
# network_management/api/views/router_management/router_session_views.py
"""
Router Session Management Views for Network Management System

This module provides API views for session recovery and user activation.
"""

import logging
import secrets
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.db.models import Q

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from network_management.models.router_management_model import (
    Router, HotspotUser, PPPoEUser, RouterSessionHistory, ActivationAttempt,
    RouterAuditLog
)
from network_management.serializers.router_management_serializer import (
    SessionRecoverySerializer, HotspotUserSerializer, PPPoEUserSerializer
)
from account.models.admin_model import Client
from internet_plans.models.plan_models import InternetPlan 
from service_operations.models.subscription_models import Subscription
from payments.models.payment_config_model import Transaction
from network_management.utils.websocket_utils import WebSocketManager
from network_management.services.hotspot_provisioning import provision_hotspot_user, provision_pppoe_user

logger = logging.getLogger(__name__)


class RouterActivateUserView(APIView):
    """
    API View for activating users on routers with payment verification.
    """
    
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """Activate a user on a router after payment verification."""
        router = Router.objects.filter(id=pk, status="connected", is_active=True).first()
        if not router:
            return Response({"error": "Router not found or not connected"}, status=status.HTTP_404_NOT_FOUND)

        payment_verified = self.verify_payment(request.data)
        if not payment_verified:
            return Response({"error": "Payment verification failed"}, status=status.HTTP_402_PAYMENT_REQUIRED)

        connection_type = request.data.get("connection_type", "hotspot")
        mac = (request.data.get("mac") or "").lower()
        username = request.data.get("username")
        password = request.data.get("password")
        plan_id = request.data.get("plan_id")
        client_id = request.data.get("client_id")
        transaction_id = request.data.get("transaction_id")

        if connection_type == "hotspot" and not all([mac, plan_id, client_id]):
            return Response({"error": "Missing required fields for hotspot"}, status=status.HTTP_400_BAD_REQUEST)
        elif connection_type == "pppoe" and not all([username, password, plan_id, client_id]):
            return Response({"error": "Missing required fields for PPPoE"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = Client.objects.get(id=client_id)
            plan = InternetPlan.objects.get(id=plan_id)
            transaction = None
            if transaction_id:
                try:
                    transaction = Transaction.objects.get(id=transaction_id)
                except Transaction.DoesNotExist:
                    transaction = None

            if connection_type == "hotspot":
                return self.activate_hotspot_user(router, client, plan, transaction, mac, request)
            elif connection_type == "pppoe":
                return self.activate_pppoe_user(router, client, plan, transaction, username, password, request)
            else:
                return Response({"error": "Invalid connection type"}, status=status.HTTP_400_BAD_REQUEST)

        except Client.DoesNotExist:
            return Response({"error": "Client not found"}, status=status.HTTP_404_NOT_FOUND)
        except InternetPlan.DoesNotExist:
            return Response({"error": "Plan not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception("Error activating user")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def verify_payment(self, data):
        """Enhanced payment verification with multiple checks."""
        try:
            client_id = data.get('client_id')
            plan_id = data.get('plan_id')
            transaction_id = data.get('transaction_id')
            
            if not all([client_id, plan_id]):
                return False

            active_subscription = Subscription.objects.filter(
                client_id=client_id,
                internet_plan_id=plan_id,
                is_active=True,
                end_date__gt=timezone.now()
            ).exists()
            
            if active_subscription:
                return True

            if transaction_id:
                try:
                    transaction = Transaction.objects.get(
                        id=transaction_id,
                        status='completed'
                    )
                    return True
                except Transaction.DoesNotExist:
                    pass

            recent_payment = Transaction.objects.filter(
                client_id=client_id,
                plan_id=plan_id,
                status='completed',
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).exists()
            
            return recent_payment

        except Exception as e:
            logger.error(f"Payment verification failed: {str(e)}")
            return False

    def activate_hotspot_user(self, router, client, plan, transaction, mac, request):
        """Activate a hotspot user on the router."""
        existing_session = HotspotUser.objects.filter(client=client, active=True).first()
        if existing_session:
            self.end_existing_session(existing_session, "router_switch")

        remaining_time = self.calculate_remaining_time(client, plan)
        hotspot_secret = secrets.token_urlsafe(16)
        username_str = client.user.username if getattr(client, "user", None) else f"user_{client.id}"

        hotspot_user = HotspotUser.objects.create(
            router=router,
            client=client,
            plan=plan,
            transaction=transaction,
            mac=mac,
            ip=request.META.get('REMOTE_ADDR', '0.0.0.0'),
            active=True,
            remaining_time=remaining_time,
            hotspot_secret=hotspot_secret,
        )

        success, error = provision_hotspot_user(
            router, mac, username_str, hotspot_secret, plan=plan, remaining_time=remaining_time
        )

        try:
            subscription, _ = Subscription.objects.get_or_create(client=client, internet_plan=plan)
        except Exception:
            subscription = None

        ActivationAttempt.objects.create(
            subscription=subscription,
            router=router,
            success=bool(success),
            error_message=error if error else "",
            retry_count=0,
            user_type="hotspot"
        )

        RouterAuditLog.objects.create(
            router=router,
            action='user_activation',
            description=f"Hotspot user activated for {client.user.username}",
            user=request.user,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            changes={'mac': mac, 'plan': plan.name, 'client': client.user.username}
        )

        if success:
            WebSocketManager.send_user_activation_notification(
                router.id, 
                'hotspot', 
                {'client': client.user.username, 'mac': mac, 'plan': plan.name}
            )
            serializer = HotspotUserSerializer(hotspot_user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            hotspot_user.delete()
            return Response({"error": error}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def activate_pppoe_user(self, router, client, plan, transaction, username, password, request):
        """Activate a PPPoE user on the router."""
        existing_session = PPPoEUser.objects.filter(client=client, active=True).first()
        if existing_session:
            self.end_existing_session(existing_session, "router_switch")

        remaining_time = self.calculate_remaining_time(client, plan)

        pppoe_user = PPPoEUser.objects.create(
            router=router,
            client=client,
            plan=plan,
            transaction=transaction,
            username=username,
            password=password,
            ip_address=request.META.get('REMOTE_ADDR', '0.0.0.0'),
            active=True,
            remaining_time=remaining_time
        )

        success, error = provision_pppoe_user(
            router, username, password, plan=plan, remote_address=pppoe_user.ip_address,
            remaining_time=remaining_time
        )

        try:
            subscription, _ = Subscription.objects.get_or_create(client=client, internet_plan=plan)
        except Exception:
            subscription = None

        ActivationAttempt.objects.create(
            subscription=subscription,
            router=router,
            success=bool(success),
            error_message=error if error else "",
            retry_count=0,
            user_type="pppoe"
        )

        RouterAuditLog.objects.create(
            router=router,
            action='user_activation',
            description=f"PPPoE user activated for {client.user.username}",
            user=request.user,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            changes={'username': username, 'plan': plan.name, 'client': client.user.username}
        )

        if success:
            WebSocketManager.send_user_activation_notification(
                router.id, 
                'pppoe', 
                {'client': client.user.username, 'username': username, 'plan': plan.name}
            )
            serializer = PPPoEUserSerializer(pppoe_user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            pppoe_user.delete()
            return Response({"error": error}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def end_existing_session(self, session, reason):
        """End an existing user session."""
        session.active = False
        session.disconnected_at = timezone.now()
        session.save()

        session_duration = int((timezone.now() - session.connected_at).total_seconds())
        user_type = "hotspot" if isinstance(session, HotspotUser) else "pppoe"
        
        RouterSessionHistory.objects.create(
            hotspot_user=session if user_type == "hotspot" else None,
            pppoe_user=session if user_type == "pppoe" else None,
            router=session.router,
            start_time=session.connected_at,
            end_time=timezone.now(),
            data_used=getattr(session, "data_used", 0),
            duration=session_duration,
            disconnected_reason=reason,
            user_type=user_type
        )

    def calculate_remaining_time(self, client, plan):
        """Calculate remaining time for a client's plan."""
        hotspot_sessions = HotspotUser.objects.filter(client=client, plan=plan, active=False)
        pppoe_sessions = PPPoEUser.objects.filter(client=client, plan=plan, active=False)

        total_used_time = 0
        for session in hotspot_sessions:
            total_used_time += getattr(session, "total_session_time", 0) or 0
        for session in pppoe_sessions:
            total_used_time += getattr(session, "total_session_time", 0) or 0

        if getattr(plan, "expiry_unit", None) == 'Hours':
            plan_duration = int(getattr(plan, "expiry_value", 0)) * 3600
        elif getattr(plan, "expiry_unit", None) == 'Days':
            plan_duration = int(getattr(plan, "expiry_value", 0)) * 86400
        else:
            plan_duration = 0

        remaining_time = max(0, plan_duration - total_used_time) if plan_duration > 0 else 0
        return remaining_time


class SessionRecoveryView(APIView):
    """
    API View for recovering lost user sessions.
    """
    
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Recover lost sessions for a user."""
        serializer = SessionRecoverySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        phone_number = data['phone_number']
        mac_address = data.get('mac_address', '')
        username = data.get('username', '')
        recovery_method = data['recovery_method']

        try:
            recoverable_sessions = self.find_recoverable_sessions(phone_number, mac_address, username)
            
            if not recoverable_sessions:
                return Response({"error": "No recoverable sessions found"}, status=status.HTTP_404_NOT_FOUND)

            recovered_sessions = []
            for session in recoverable_sessions:
                if self.recover_session(session, recovery_method):
                    recovered_sessions.append(session.id)

            WebSocketManager.send_session_recovery_notification(len(recovered_sessions))
            
            return Response({
                "message": f"Recovered {len(recovered_sessions)} sessions",
                "recovered_count": len(recovered_sessions),
                "recovered_sessions": recovered_sessions
            })

        except Exception as e:
            logger.error(f"Session recovery failed: {str(e)}")
            return Response({"error": "Session recovery failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def find_recoverable_sessions(self, phone_number, mac_address, username):
        """Find sessions that can be recovered."""
        cutoff_time = timezone.now() - timedelta(hours=24)
        
        sessions = RouterSessionHistory.objects.filter(
            Q(start_time__gte=cutoff_time),
            Q(recoverable=True),
            Q(recovery_attempted=False),
            Q(disconnected_reason__in=['router_reboot', 'power_outage', 'router_switch'])
        )

        if mac_address:
            sessions = sessions.filter(
                Q(hotspot_user__mac=mac_address) | 
                Q(hotspot_user__client__user__phone_number=phone_number)
            )
        elif username:
            sessions = sessions.filter(
                Q(pppoe_user__username=username) |
                Q(pppoe_user__client__user__phone_number=phone_number)
            )
        else:
            sessions = sessions.filter(
                Q(hotspot_user__client__user__phone_number=phone_number) |
                Q(pppoe_user__client__user__phone_number=phone_number)
            )

        return sessions

    def recover_session(self, session, recovery_method):
        """Recover a single session."""
        try:
            if session.user_type == 'hotspot' and session.hotspot_user:
                return self.recover_hotspot_session(session.hotspot_user, recovery_method)
            elif session.user_type == 'pppoe' and session.pppoe_user:
                return self.recover_pppoe_session(session.pppoe_user, recovery_method)
            return False
        except Exception as e:
            logger.error(f"Session recovery failed for {session.id}: {str(e)}")
            session.recovery_attempted = True
            session.save()
            return False

    def recover_hotspot_session(self, hotspot_user, recovery_method):
        """Recover hotspot session."""
        try:
            recovered_secret = hotspot_user.hotspot_secret or secrets.token_urlsafe(16)
            new_hotspot_user = HotspotUser.objects.create(
                router=hotspot_user.router,
                client=hotspot_user.client,
                plan=hotspot_user.plan,
                transaction=hotspot_user.transaction,
                mac=hotspot_user.mac,
                ip=hotspot_user.ip,
                active=True,
                remaining_time=hotspot_user.remaining_time,
                hotspot_secret=recovered_secret,
            )

            username = getattr(hotspot_user.client, "user", None)
            username_str = username.username if username else f"user_{hotspot_user.client.id}"
            success, error = provision_hotspot_user(
                hotspot_user.router, hotspot_user.mac, username_str, recovered_secret,
                plan=hotspot_user.plan, remaining_time=hotspot_user.remaining_time
            )

            if success:
                hotspot_user.recovery_attempted = True
                hotspot_user.save()
                return True
            else:
                new_hotspot_user.delete()
                return False
        except Exception as e:
            logger.error(f"Hotspot session recovery failed: {str(e)}")
            return False

    def recover_pppoe_session(self, pppoe_user, recovery_method):
        """Recover PPPoE session."""
        try:
            new_pppoe_user = PPPoEUser.objects.create(
                router=pppoe_user.router,
                client=pppoe_user.client,
                plan=pppoe_user.plan,
                transaction=pppoe_user.transaction,
                username=pppoe_user.username,
                password=pppoe_user.password,
                ip_address=pppoe_user.ip_address,
                active=True,
                remaining_time=pppoe_user.remaining_time
            )

            success, error = provision_pppoe_user(
                pppoe_user.router, pppoe_user.username, pppoe_user.password,
                plan=pppoe_user.plan, remote_address=pppoe_user.ip_address,
                remaining_time=pppoe_user.remaining_time
            )

            if success:
                pppoe_user.recovery_attempted = True
                pppoe_user.save()
                return True
            else:
                new_pppoe_user.delete()
                return False
        except Exception as e:
            logger.error(f"PPPoE session recovery failed: {str(e)}")
            return False