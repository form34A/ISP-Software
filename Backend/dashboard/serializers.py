








# from rest_framework import serializers
# from django.db.models import Sum, Count, Avg, Q
# from django.utils import timezone
# from datetime import timedelta
# import logging

# logger = logging.getLogger(__name__)

# # Import existing models to avoid duplication
# from payments.models.transaction_log_model import TransactionLog
# from payments.models.payment_reconciliation_model import ReconciliationStats
# from internet_plans.models.create_plan_models import InternetPlan, Subscription
# from network_management.models.router_management_model import (
#     Router, RouterStats, HotspotUser, PPPoEUser, RouterHealthCheck,
#     RouterConnectionTest
# )
# from account.models.admin_model import Client

# class GridItemSerializer(serializers.Serializer):
#     id = serializers.IntegerField()
#     label = serializers.CharField()
#     value = serializers.CharField()
#     comparison = serializers.CharField()
#     icon = serializers.CharField()
#     rate = serializers.FloatField()
#     trend = serializers.CharField()
#     bgColor = serializers.CharField()
#     iconColor = serializers.CharField()
#     borderColor = serializers.CharField()
#     fontStyle = serializers.CharField()

# class SystemLoadSerializer(serializers.Serializer):
#     api_response_time = serializers.IntegerField()
#     api_comparison = serializers.CharField()
#     bandwidth_used = serializers.FloatField()
#     bandwidth_total = serializers.FloatField()
#     bandwidth_comparison = serializers.CharField()
#     cpu_load = serializers.FloatField()
#     cpu_comparison = serializers.CharField()
#     memory_load = serializers.FloatField()
#     memory_comparison = serializers.CharField()
#     router_status = serializers.CharField()
#     router_uptime = serializers.CharField()
#     upload_throughput = serializers.FloatField()
#     download_throughput = serializers.FloatField()
#     throughput_comparison = serializers.CharField()
#     router_temperature = serializers.FloatField()
#     temperature_comparison = serializers.CharField()
#     firmware_version = serializers.CharField()
#     firmware_comparison = serializers.CharField()
#     status = serializers.CharField()

# class MonthlyDataSerializer(serializers.Serializer):
#     month = serializers.CharField()
#     value = serializers.FloatField()

# class PlanDataSerializer(serializers.Serializer):
#     plan = serializers.CharField()
#     users = serializers.IntegerField()
#     revenue = serializers.FloatField()
#     avg_data_usage = serializers.FloatField()

# class SalesDataSerializer(serializers.Serializer):
#     month = serializers.CharField()
#     plan = serializers.CharField()
#     sales = serializers.IntegerField()

# class RevenueDataSerializer(serializers.Serializer):
#     month = serializers.CharField()
#     targeted_revenue = serializers.FloatField()
#     projected_revenue = serializers.FloatField()

# class FinancialDataSerializer(serializers.Serializer):
#     month = serializers.CharField()
#     income = serializers.FloatField()
#     profit = serializers.FloatField()
#     expenses = serializers.FloatField()

# class DataUsageSerializer(serializers.Serializer):
#     month = serializers.CharField()
#     hotspot_data = serializers.FloatField()
#     pppoe_data = serializers.FloatField()
#     total_data = serializers.FloatField()

# class ClientTypeSerializer(serializers.Serializer):
#     type = serializers.CharField()
#     count = serializers.IntegerField()
#     percentage = serializers.FloatField()

# class RouterHealthSerializer(serializers.Serializer):
#     router_name = serializers.CharField()
#     ip = serializers.CharField()
#     status = serializers.CharField()
#     health_score = serializers.FloatField()
#     active_users = serializers.IntegerField()
#     last_seen = serializers.DateTimeField()

# class DashboardSerializer(serializers.Serializer):
#     grid_items = GridItemSerializer(many=True)
#     system_load = SystemLoadSerializer()
#     sales_data = SalesDataSerializer(many=True)
#     revenue_data = RevenueDataSerializer(many=True)
#     financial_data = FinancialDataSerializer(many=True)
#     visitor_data = serializers.DictField()
#     plan_performance = PlanDataSerializer(many=True)
#     new_subscriptions = MonthlyDataSerializer(many=True)
#     data_usage = DataUsageSerializer(many=True)
#     client_types = ClientTypeSerializer(many=True)
#     router_health = RouterHealthSerializer(many=True)

# class DashboardDataService:
#     """Enhanced data service that integrates all existing apps"""
    
#     @staticmethod
#     def calculate_percentage_change(current, previous):
#         """Calculate percentage change safely."""
#         if previous == 0:
#             return 100.0 if current > 0 else 0.0
#         return ((current - previous) / previous) * 100.0

#     @staticmethod
#     def get_trend_direction(current, previous):
#         """Determine trend direction."""
#         return "up" if current > previous else "down"

#     @staticmethod
#     def format_currency(amount, currency='KES'):
#         """Format currency for display."""
#         if amount is None:
#             amount = 0
#         return f"{currency} {amount:,.0f}"

#     @staticmethod
#     def get_client_metrics():
#         """Get comprehensive client and user metrics."""
#         try:
#             # Active users from network management
#             active_hotspot_users = HotspotUser.objects.filter(active=True).count()
#             active_pppoe_users = PPPoEUser.objects.filter(active=True).count()
#             total_active_users = active_hotspot_users + active_pppoe_users
            
#             # Client counts
#             hotspot_clients = HotspotUser.objects.values('client').distinct().count()
#             pppoe_clients = PPPoEUser.objects.values('client').distinct().count()
#             total_clients = hotspot_clients + pppoe_clients
            
#             # Registered clients
#             total_registered_clients = Client.objects.count()
            
#             return {
#                 'active_hotspot_users': active_hotspot_users,
#                 'active_pppoe_users': active_pppoe_users,
#                 'total_active_users': total_active_users,
#                 'hotspot_clients': hotspot_clients,
#                 'pppoe_clients': pppoe_clients,
#                 'total_clients': total_clients,
#                 'registered_clients': total_registered_clients
#             }
#         except Exception as e:
#             logger.error(f"Error getting client metrics: {e}")
#             return {
#                 'active_hotspot_users': 0, 'active_pppoe_users': 0, 'total_active_users': 0,
#                 'hotspot_clients': 0, 'pppoe_clients': 0, 'total_clients': 0, 'registered_clients': 0
#             }

#     @staticmethod
#     def get_payment_metrics():
#         """Get payment and revenue metrics from payment reconciliation."""
#         try:
#             now = timezone.now()
#             today = now.replace(hour=0, minute=0, second=0, microsecond=0)
#             yesterday = today - timedelta(days=1)
#             last_month = today - timedelta(days=30)
            
#             # Transaction data
#             transactions = TransactionLog.objects.filter(status='success')
            
#             revenue_data = transactions.aggregate(
#                 total_revenue=Sum('amount'),
#                 today_revenue=Sum('amount', filter=Q(created_at__gte=today)),
#                 yesterday_revenue=Sum('amount', filter=Q(created_at__gte=yesterday, created_at__lt=today)),
#                 last_month_revenue=Sum('amount', filter=Q(created_at__gte=last_month, created_at__lt=today))
#             )
            
#             # Reconciliation stats
#             reconciliation_stats = ReconciliationStats.objects.filter(
#                 date__gte=last_month
#             ).aggregate(
#                 total_profit=Sum('net_profit'),
#                 total_expenses=Sum('total_expenses')
#             )
            
#             return {
#                 'total_revenue': revenue_data['total_revenue'] or 0,
#                 'today_revenue': revenue_data['today_revenue'] or 0,
#                 'yesterday_revenue': revenue_data['yesterday_revenue'] or 0,
#                 'last_month_revenue': revenue_data['last_month_revenue'] or 0,
#                 'total_profit': reconciliation_stats['total_profit'] or 0,
#                 'total_expenses': reconciliation_stats['total_expenses'] or 0
#             }
#         except Exception as e:
#             logger.error(f"Error getting payment metrics: {e}")
#             return {
#                 'total_revenue': 0, 'today_revenue': 0, 'yesterday_revenue': 0,
#                 'last_month_revenue': 0, 'total_profit': 0, 'total_expenses': 0
#             }

#     @staticmethod
#     def get_router_metrics():
#         """Get comprehensive router health metrics."""
#         try:
#             routers = Router.objects.filter(is_active=True)
#             online_routers = routers.filter(connection_status='connected').count()
            
#             # Recent health checks
#             recent_health_checks = RouterHealthCheck.objects.filter(
#                 timestamp__gte=timezone.now() - timedelta(hours=1)
#             )
            
#             avg_health_score = recent_health_checks.aggregate(
#                 avg_score=Avg('health_score')
#             )['avg_score'] or 0
            
#             return {
#                 'total_routers': routers.count(),
#                 'online_routers': online_routers,
#                 'avg_health_score': avg_health_score,
#                 'online_percentage': (online_routers / routers.count() * 100) if routers.count() > 0 else 0
#             }
#         except Exception as e:
#             logger.error(f"Error getting router metrics: {e}")
#             return {'total_routers': 0, 'online_routers': 0, 'avg_health_score': 0, 'online_percentage': 0}

#     @staticmethod
#     def get_connection_metrics():
#         """Get connection quality metrics."""
#         try:
#             recent_tests = RouterConnectionTest.objects.filter(
#                 tested_at__gte=timezone.now() - timedelta(days=7)
#             )
            
#             if recent_tests.exists():
#                 total_tests = recent_tests.count()
#                 successful_tests = recent_tests.filter(success=True).count()
#                 success_rate = (successful_tests / total_tests) * 100
                
#                 successful_response_times = recent_tests.filter(
#                     success=True, response_time__isnull=False
#                 ).values_list('response_time', flat=True)
                
#                 avg_response_time = sum(successful_response_times) / len(successful_response_times) if successful_response_times else 0
                
#                 return {
#                     'success_rate': success_rate,
#                     'avg_response_time': avg_response_time,
#                     'total_tests': total_tests
#                 }
#         except Exception as e:
#             logger.error(f"Error getting connection metrics: {e}")
        
#         return {'success_rate': 0, 'avg_response_time': 0, 'total_tests': 0}

#     @staticmethod
#     def get_plan_metrics():
#         """Get internet plan performance metrics."""
#         try:
#             subscriptions = Subscription.objects.select_related('internet_plan')
#             active_subscriptions = subscriptions.filter(status='active')
            
#             plan_performance = []
#             for plan in InternetPlan.objects.all()[:6]:  # Limit to top 6 plans
#                 plan_subs = active_subscriptions.filter(internet_plan=plan)
#                 plan_revenue = TransactionLog.objects.filter(
#                     subscription__internet_plan=plan, status='success'
#                 ).aggregate(total=Sum('amount'))['total'] or 0
                
#                 plan_performance.append({
#                     'plan': plan.name,
#                     'users': plan_subs.count(),
#                     'revenue': float(plan_revenue),
#                     'avg_data_usage': float(plan.data_limit_value or 0)
#                 })
            
#             return plan_performance
#         except Exception as e:
#             logger.error(f"Error getting plan metrics: {e}")
#             return []

#     @staticmethod
#     def get_system_load_metrics():
#         """Get real system load metrics from routers."""
#         try:
#             now = timezone.now()
            
#             # Router statistics
#             router_stats = RouterStats.objects.filter(
#                 timestamp__gte=now - timedelta(hours=1)
#             ).aggregate(
#                 avg_cpu=Avg('cpu'),
#                 avg_memory=Avg('memory'),
#                 avg_upload=Avg('upload_speed'),
#                 avg_download=Avg('download_speed'),
#                 avg_throughput=Avg('throughput')
#             )

#             # API response times
#             api_response_data = RouterConnectionTest.objects.filter(
#                 tested_at__gte=now - timedelta(hours=1),
#                 success=True
#             ).aggregate(
#                 avg_response=Avg('response_time')
#             )

#             router_metrics = DashboardDataService.get_router_metrics()

#             return {
#                 "api_response_time": int((api_response_data['avg_response'] or 0) * 1000),
#                 "api_comparison": "Real-time API monitoring",
#                 "bandwidth_used": float(router_stats['avg_throughput'] or 0),
#                 "bandwidth_total": 1000.0,
#                 "bandwidth_comparison": "Total network capacity",
#                 "cpu_load": float(router_stats['avg_cpu'] or 0),
#                 "cpu_comparison": "Average across all routers",
#                 "memory_load": float(router_stats['avg_memory'] or 0),
#                 "memory_comparison": "Average across all routers",
#                 "router_status": "online" if router_metrics['online_routers'] > 0 else "offline",
#                 "router_uptime": "Real-time monitoring",
#                 "upload_throughput": float(router_stats['avg_upload'] or 0),
#                 "download_throughput": float(router_stats['avg_download'] or 0),
#                 "throughput_comparison": "Current network traffic",
#                 "router_temperature": 45.0,  # Could be enhanced with actual temperature data
#                 "temperature_comparison": "Normal operating range",
#                 "firmware_version": "v6.49.6",
#                 "firmware_comparison": "Latest stable",
#                 "status": "operational" if router_metrics['online_percentage'] > 90 else "degraded"
#             }
#         except Exception as e:
#             logger.error(f"Error getting system load metrics: {e}")
#             return {
#                 "api_response_time": 0, "api_comparison": "N/A", "bandwidth_used": 0,
#                 "bandwidth_total": 0, "bandwidth_comparison": "N/A", "cpu_load": 0,
#                 "cpu_comparison": "N/A", "memory_load": 0, "memory_comparison": "N/A",
#                 "router_status": "unknown", "router_uptime": "N/A", "upload_throughput": 0,
#                 "download_throughput": 0, "throughput_comparison": "N/A", "router_temperature": 0,
#                 "temperature_comparison": "N/A", "firmware_version": "Unknown",
#                 "firmware_comparison": "N/A", "status": "unknown"
#             }






from rest_framework import serializers
from django.db.models import Sum, Count, Avg, Q, Max, F
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

# Import existing models to avoid duplication
from payments.models.transaction_log_model import TransactionLog
from payments.models.payment_reconciliation_model import ReconciliationStats
from internet_plans.models.plan_models import InternetPlan, PlanTemplate
from service_operations.models.subscription_models import Subscription
from network_management.models.router_management_model import (
    Router, RouterStats, HotspotUser, PPPoEUser, RouterHealthCheck,
    RouterConnectionTest
)
from network_management.models.wan_sample_model import WanSample
from account.models.admin_model import Client

class GridItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField()
    value = serializers.CharField()
    comparison = serializers.CharField()
    icon = serializers.CharField()
    rate = serializers.FloatField()
    trend = serializers.CharField()
    bgColor = serializers.CharField()
    iconColor = serializers.CharField()
    borderColor = serializers.CharField()
    fontStyle = serializers.CharField()

class SystemLoadSerializer(serializers.Serializer):
    api_response_time = serializers.IntegerField()
    api_comparison = serializers.CharField()
    bandwidth_used = serializers.FloatField(allow_null=True)
    bandwidth_total = serializers.FloatField(allow_null=True)
    bandwidth_comparison = serializers.CharField()
    cpu_load = serializers.FloatField()
    cpu_comparison = serializers.CharField()
    memory_load = serializers.FloatField()
    memory_comparison = serializers.CharField()
    router_status = serializers.CharField()
    router_uptime = serializers.CharField()
    upload_throughput = serializers.FloatField(allow_null=True)
    download_throughput = serializers.FloatField(allow_null=True)
    throughput_comparison = serializers.CharField()
    router_temperature = serializers.FloatField(allow_null=True)
    temperature_comparison = serializers.CharField()
    firmware_version = serializers.CharField(allow_null=True)
    firmware_comparison = serializers.CharField()
    status = serializers.CharField()

class MonthlyDataSerializer(serializers.Serializer):
    month = serializers.CharField()
    value = serializers.FloatField()

class PlanDataSerializer(serializers.Serializer):
    plan = serializers.CharField()
    users = serializers.IntegerField()
    revenue = serializers.FloatField()
    avg_data_usage = serializers.FloatField()

class SalesDataSerializer(serializers.Serializer):
    month = serializers.CharField()
    plan = serializers.CharField()
    sales = serializers.IntegerField()

class RevenueDataSerializer(serializers.Serializer):
    month = serializers.CharField()
    targeted_revenue = serializers.FloatField()
    projected_revenue = serializers.FloatField()

class FinancialDataSerializer(serializers.Serializer):
    month = serializers.CharField()
    income = serializers.FloatField()
    profit = serializers.FloatField()
    expenses = serializers.FloatField()

class DataUsageSerializer(serializers.Serializer):
    month = serializers.CharField()
    hotspot_data = serializers.FloatField()
    pppoe_data = serializers.FloatField()
    total_data = serializers.FloatField()

class ClientTypeSerializer(serializers.Serializer):
    type = serializers.CharField()
    count = serializers.IntegerField()
    percentage = serializers.FloatField()

class RouterHealthSerializer(serializers.Serializer):
    router_name = serializers.CharField()
    ip = serializers.CharField()
    status = serializers.CharField()
    health_score = serializers.FloatField()
    active_users = serializers.IntegerField()
    last_seen = serializers.DateTimeField()
class DashboardSerializer(serializers.Serializer):
    grid_items = GridItemSerializer(many=True, default=[])
    system_load = SystemLoadSerializer(default=dict)
    sales_data = SalesDataSerializer(many=True, default=[])
    revenue_data = RevenueDataSerializer(many=True, default=[])
    financial_data = FinancialDataSerializer(many=True, default=[])
    visitor_data = serializers.DictField(default=dict)
    plan_performance = PlanDataSerializer(many=True, default=[])
    new_subscriptions = MonthlyDataSerializer(many=True, default=[])
    data_usage = DataUsageSerializer(many=True, default=[])
    client_types = ClientTypeSerializer(many=True, default=[])
    router_health = RouterHealthSerializer(many=True, default=[])

class DashboardDataService:
    """Enhanced data service that integrates all existing apps with real dynamic data"""

    # Mirrors sample_wan.py's DEFAULT_ROUTER_ID/--interface default, so the
    # dashboard reads WAN samples from the same router+interface the
    # collector actually writes - a second sampled router/interface can't
    # silently blend into these numbers.
    DEFAULT_WAN_ROUTER_ID = 6
    DEFAULT_WAN_INTERFACE = 'ether1'

    @staticmethod
    def _resolve_wan_router_id():
        """
        Same fallback chain as sample_wan.py's _resolve_router: prefer the
        known default WAN router if it's active, else fall back to the
        single active router if there's exactly one. Returns None (callers
        show "No recent data") rather than guessing across an ambiguous fleet.
        """
        if Router.objects.filter(
            pk=DashboardDataService.DEFAULT_WAN_ROUTER_ID, is_active=True
        ).exists():
            return DashboardDataService.DEFAULT_WAN_ROUTER_ID

        active_router_ids = list(
            Router.objects.filter(is_active=True).values_list('id', flat=True)
        )
        if len(active_router_ids) == 1:
            return active_router_ids[0]
        return None


    @staticmethod
    def calculate_percentage_change(current, previous):
        """Calculate percentage change safely."""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return ((current - previous) / previous) * 100.0

    @staticmethod
    def get_trend_direction(current, previous):
        """Determine trend direction."""
        return "up" if current > previous else "down"

    @staticmethod
    def format_currency(amount, currency='KES'):
        """Format currency for display."""
        if amount is None:
            amount = 0
        return f"{currency} {amount:,.0f}"

    @staticmethod
    def get_client_metrics():
        """Get comprehensive client and user metrics with real data."""
        try:
            # Active users from network management
            active_hotspot_users = HotspotUser.objects.filter(active=True).count()
            active_pppoe_users = PPPoEUser.objects.filter(active=True).count()
            total_active_users = active_hotspot_users + active_pppoe_users
            
            # Client counts from subscriptions
            unique_hotspot_clients = Subscription.objects.filter(
                access_method='hotspot',
                status='active',
                is_active=True
            ).values('client_id').distinct().count()

            unique_pppoe_clients = Subscription.objects.filter(
                access_method='pppoe',
                status='active',
                is_active=True
            ).values('client_id').distinct().count()
            
            total_clients = unique_hotspot_clients + unique_pppoe_clients
            
            # Registered clients
            total_registered_clients = Client.objects.count()
            
            return {
                'active_hotspot_users': active_hotspot_users,
                'active_pppoe_users': active_pppoe_users,
                'total_active_users': total_active_users,
                'hotspot_clients': unique_hotspot_clients,
                'pppoe_clients': unique_pppoe_clients,
                'total_clients': total_clients,
                'registered_clients': total_registered_clients
            }
        except Exception as e:
            logger.error(f"Error getting client metrics: {e}")
            return {
                'active_hotspot_users': 0, 'active_pppoe_users': 0, 'total_active_users': 0,
                'hotspot_clients': 0, 'pppoe_clients': 0, 'total_clients': 0, 'registered_clients': 0
            }

    @staticmethod
    def get_payment_metrics():
        """Get payment and revenue metrics from payment reconciliation with real transaction data."""
        try:
            now = timezone.now()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday = today - timedelta(days=1)
            last_month = today - timedelta(days=30)
            last_week = today - timedelta(days=7)
            
            # Transaction data with access type breakdown
            transactions = TransactionLog.objects.filter(status='success')
            
            revenue_data = transactions.aggregate(
                total_revenue=Sum('amount'),
                today_revenue=Sum('amount', filter=Q(created_at__gte=today)),
                yesterday_revenue=Sum('amount', filter=Q(created_at__gte=yesterday, created_at__lt=today)),
                last_month_revenue=Sum('amount', filter=Q(created_at__gte=last_month, created_at__lt=today)),
                last_week_revenue=Sum('amount', filter=Q(created_at__gte=last_week, created_at__lt=today))
            )
            
            # Access type revenue breakdown
            hotspot_revenue = transactions.filter(
                access_type='hotspot'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            pppoe_revenue = transactions.filter(
                access_type='pppoe'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            both_revenue = transactions.filter(
                access_type='both'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            # Reconciliation stats
            reconciliation_stats = ReconciliationStats.objects.filter(
                date__gte=last_month
            ).aggregate(
                total_profit=Sum('net_profit'),
                total_expenses=Sum('total_expenses')
            )
            
            return {
                'total_revenue': revenue_data['total_revenue'] or 0,
                'today_revenue': revenue_data['today_revenue'] or 0,
                'yesterday_revenue': revenue_data['yesterday_revenue'] or 0,
                'last_month_revenue': revenue_data['last_month_revenue'] or 0,
                'last_week_revenue': revenue_data['last_week_revenue'] or 0,
                'total_profit': reconciliation_stats['total_profit'] or 0,
                'total_expenses': reconciliation_stats['total_expenses'] or 0,
                'hotspot_revenue': hotspot_revenue,
                'pppoe_revenue': pppoe_revenue,
                'both_revenue': both_revenue
            }
        except Exception as e:
            logger.error(f"Error getting payment metrics: {e}")
            return {
                'total_revenue': 0, 'today_revenue': 0, 'yesterday_revenue': 0,
                'last_month_revenue': 0, 'last_week_revenue': 0, 'total_profit': 0, 
                'total_expenses': 0, 'hotspot_revenue': 0, 'pppoe_revenue': 0, 'both_revenue': 0
            }

    @staticmethod
    def get_router_metrics():
        """Get comprehensive router health metrics with real data."""
        try:
            now = timezone.now()
            stale_cutoff = now - timedelta(minutes=10)

            routers = Router.objects.filter(is_active=True)
            total_routers = routers.count()

            # A router only counts as genuinely "online" if it's both marked
            # connected AND has reported in within the last ~10 minutes -
            # otherwise a stopped collector leaves connection_status stuck on
            # 'connected' looking falsely healthy forever. Routers that are
            # still marked connected but haven't reported recently are
            # "stale" (status-unknown), distinct from a router that actually
            # failed to connect.
            online_routers = routers.filter(
                connection_status='connected', last_seen__gte=stale_cutoff
            ).count()
            stale_routers = routers.filter(
                connection_status='connected', last_seen__lt=stale_cutoff
            ).count()

            if online_routers > 0:
                router_status = "online"
            elif stale_routers > 0:
                router_status = "unknown"
            else:
                router_status = "offline"

            # Recent health checks
            recent_health_checks = RouterHealthCheck.objects.filter(
                timestamp__gte=now - timedelta(hours=1)
            )

            avg_health_score = recent_health_checks.aggregate(
                avg_score=Avg('health_score')
            )['avg_score'] or 0

            # Router capacity and load
            total_capacity = routers.aggregate(
                total_capacity=Sum('max_clients')
            )['total_capacity'] or 0

            # Router has no current_clients field; mirror Router.get_active_users_count()
            # (hotspot_users + pppoe_users active counts) across the whole queryset.
            current_load = (
                HotspotUser.objects.filter(router__in=routers, active=True).count() +
                PPPoEUser.objects.filter(router__in=routers, active=True).count()
            )

            load_percentage = (current_load / total_capacity * 100) if total_capacity > 0 else 0

            return {
                'total_routers': total_routers,
                'online_routers': online_routers,
                'stale_routers': stale_routers,
                'router_status': router_status,
                'avg_health_score': avg_health_score,
                'online_percentage': (online_routers / total_routers * 100) if total_routers > 0 else 0,
                'total_capacity': total_capacity,
                'current_load': current_load,
                'load_percentage': load_percentage
            }
        except Exception as e:
            logger.error(f"Error getting router metrics: {e}")
            return {
                'total_routers': 0, 'online_routers': 0, 'stale_routers': 0, 'router_status': 'unknown',
                'avg_health_score': 0, 'online_percentage': 0, 'total_capacity': 0, 'current_load': 0, 'load_percentage': 0
            }

    @staticmethod
    def get_connection_metrics():
        """Get connection quality metrics with real test data."""
        try:
            recent_tests = RouterConnectionTest.objects.filter(
                tested_at__gte=timezone.now() - timedelta(days=7)
            )
            
            if recent_tests.exists():
                total_tests = recent_tests.count()
                successful_tests = recent_tests.filter(success=True).count()
                success_rate = (successful_tests / total_tests) * 100
                
                successful_response_times = recent_tests.filter(
                    success=True, response_time__isnull=False
                ).values_list('response_time', flat=True)
                
                avg_response_time = sum(successful_response_times) / len(successful_response_times) if successful_response_times else 0

                return {
                    'success_rate': success_rate,
                    'avg_response_time': avg_response_time,
                    'total_tests': total_tests,
                }
        except Exception as e:
            logger.error(f"Error getting connection metrics: {e}")

        return {
            'success_rate': 0, 'avg_response_time': 0, 'total_tests': 0,
        }

    @staticmethod
    def get_plan_metrics():
        """Get internet plan performance metrics with real subscription data."""
        try:
            subscriptions = Subscription.objects.select_related('internet_plan')
            active_subscriptions = subscriptions.filter(status='active', is_active=True)
            
            plan_performance = []
            for plan in InternetPlan.objects.filter(active=True)[:8]:  # Top 8 active plans
                plan_subs = active_subscriptions.filter(internet_plan=plan)
                
                # Revenue from successful transactions for this plan
                plan_revenue = TransactionLog.objects.filter(
                    subscription__internet_plan=plan, 
                    status='success'
                ).aggregate(total=Sum('amount'))['total'] or 0
                
                # Access type breakdown
                hotspot_subs = plan_subs.filter(access_method='hotspot').count()
                pppoe_subs = plan_subs.filter(access_method='pppoe').count()
                
                # Average data usage (placeholder - would integrate with actual usage data)
                avg_data_usage = plan.purchases * 1024 * 1024 * 1024  # 1GB per purchase as example
                
                plan_performance.append({
                    'plan': plan.name,
                    'users': plan_subs.count(),
                    'revenue': float(plan_revenue),
                    'avg_data_usage': float(avg_data_usage / (1024**3)),  # Convert to GB
                    'hotspot_users': hotspot_subs,
                    'pppoe_users': pppoe_subs,
                    'purchases': plan.purchases,
                    'price': float(plan.price),
                    'category': plan.category
                })
            
            return plan_performance
        except Exception as e:
            logger.error(f"Error getting plan metrics: {e}")
            return []

    @staticmethod
    def _wan_trend_label(now, aggregate_expr, router_id, interface):
        """
        Compare a WanSample metric's average over the last 10 minutes against
        the preceding 10-minute window and return an honest "up/down X% vs
        previous 10 min" label - or None if either window lacks data to
        compare (never a fabricated percentage). Scoped to a single
        router+interface so a second sampled WAN link can't blend in.
        """
        recent = WanSample.objects.filter(
            router_id=router_id, interface=interface,
            timestamp__gte=now - timedelta(minutes=10)
        ).aggregate(avg=aggregate_expr)['avg']

        preceding = WanSample.objects.filter(
            router_id=router_id, interface=interface,
            timestamp__gte=now - timedelta(minutes=20),
            timestamp__lt=now - timedelta(minutes=10)
        ).aggregate(avg=aggregate_expr)['avg']

        if recent is None or preceding is None or preceding == 0:
            return None

        pct_change = (recent - preceding) / preceding * 100
        direction = "up" if pct_change >= 0 else "down"
        return f"{direction} {abs(pct_change):.1f}% vs previous 10 min"

    @staticmethod
    def get_system_load_metrics():
        """Get real system load metrics from routers and network data."""
        try:
            now = timezone.now()

            # Router statistics
            router_stats = RouterStats.objects.filter(
                timestamp__gte=now - timedelta(hours=1)
            ).aggregate(
                avg_cpu=Avg('cpu'),
                avg_memory=Avg('memory'),
                max_cpu=Max('cpu'),
                max_memory=Max('memory')
            )

            # API response times from connection tests
            api_response_data = RouterConnectionTest.objects.filter(
                tested_at__gte=now - timedelta(hours=1),
                success=True
            ).aggregate(
                avg_response=Avg('response_time'),
                max_response=Max('response_time')
            )

            router_metrics = DashboardDataService.get_router_metrics()

            # Temperature/firmware come from whichever router most recently reported
            # RouterStats within the same window the other system-load metrics use above.
            latest_stats = RouterStats.objects.filter(
                timestamp__gte=now - timedelta(hours=1)
            ).select_related('router').order_by('-timestamp').first()

            router_temperature = latest_stats.temperature if latest_stats else None
            firmware_version = latest_stats.router.firmware_version if latest_stats and latest_stats.router else None

            # Bandwidth/throughput come from real WAN samples (sample_wan),
            # not a synthetic estimate. Scoped to the single active WAN
            # router+interface (same resolution sample_wan itself uses) so a
            # second sampled router/interface can't skew these numbers. A
            # sample must be within the last 10 minutes to count as
            # "current" - otherwise these stay None rather than showing a
            # stale or fabricated number.
            wan_router_id = DashboardDataService._resolve_wan_router_id()
            wan_interface = DashboardDataService.DEFAULT_WAN_INTERFACE

            if wan_router_id is not None:
                latest_wan_sample = WanSample.objects.filter(
                    router_id=wan_router_id, interface=wan_interface,
                    timestamp__gte=now - timedelta(minutes=10),
                    down_mbps__isnull=False
                ).order_by('-timestamp').first()

                bandwidth_total = WanSample.objects.filter(
                    router_id=wan_router_id, interface=wan_interface,
                    timestamp__gte=now - timedelta(days=7),
                    down_mbps__isnull=False
                ).aggregate(peak=Max('down_mbps'))['peak']

                bandwidth_trend = DashboardDataService._wan_trend_label(
                    now, Avg('down_mbps'), wan_router_id, wan_interface
                )
                throughput_trend = DashboardDataService._wan_trend_label(
                    now, Avg(F('down_mbps') + F('up_mbps')), wan_router_id, wan_interface
                )
            else:
                # Fleet is ambiguous (no default router active, more than
                # one other active router) - don't guess which WAN link to
                # read from.
                latest_wan_sample = None
                bandwidth_total = None
                bandwidth_trend = None
                throughput_trend = None

            bandwidth_used = latest_wan_sample.down_mbps if latest_wan_sample else None
            download_throughput = latest_wan_sample.down_mbps if latest_wan_sample else None
            upload_throughput = latest_wan_sample.up_mbps if latest_wan_sample else None

            return {
                "api_response_time": int((api_response_data['avg_response'] or 0) * 1000),
                "api_comparison": f"Max: {int((api_response_data['max_response'] or 0) * 1000)}ms",
                "bandwidth_used": bandwidth_used,
                "bandwidth_total": bandwidth_total,
                "bandwidth_comparison": bandwidth_trend or "No recent data",
                "cpu_load": float(router_stats['avg_cpu'] or 0),
                "cpu_comparison": f"Peak: {router_stats['max_cpu'] or 0}%",
                "memory_load": float(router_stats['avg_memory'] or 0),
                "memory_comparison": f"Peak: {router_stats['max_memory'] or 0}%",
                "router_status": router_metrics['router_status'],
                "router_uptime": f"{router_metrics['online_routers']}/{router_metrics['total_routers']} online",
                "upload_throughput": upload_throughput,
                "download_throughput": download_throughput,
                "throughput_comparison": throughput_trend or "No recent data",
                "router_temperature": router_temperature,
                "temperature_comparison": "Normal operating range" if router_temperature is not None else "No recent data",
                "firmware_version": firmware_version,
                "firmware_comparison": "Latest stable" if firmware_version else "No recent data",
                "status": "operational" if router_metrics['online_percentage'] > 90 else "degraded"
            }
        except Exception as e:
            logger.error(f"Error getting system load metrics: {e}")
            return {
                "api_response_time": 0, "api_comparison": "N/A", "bandwidth_used": None,
                "bandwidth_total": None, "bandwidth_comparison": "N/A", "cpu_load": 0,
                "cpu_comparison": "N/A", "memory_load": 0, "memory_comparison": "N/A",
                "router_status": "unknown", "router_uptime": "N/A", "upload_throughput": None,
                "download_throughput": None, "throughput_comparison": "N/A", "router_temperature": None,
                "temperature_comparison": "N/A", "firmware_version": None,
                "firmware_comparison": "N/A", "status": "unknown"
            }

    @staticmethod
    def get_subscription_metrics():
        """Get comprehensive subscription metrics."""
        try:
            now = timezone.now()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            last_week = today - timedelta(days=7)
            last_month = today - timedelta(days=30)
            
            subscriptions = Subscription.objects.all()
            active_subscriptions = subscriptions.filter(status='active', is_active=True)
            
            metrics = {
                'total_subscriptions': subscriptions.count(),
                'active_subscriptions': active_subscriptions.count(),
                'pending_subscriptions': subscriptions.filter(status='pending').count(),
                'expired_subscriptions': subscriptions.filter(status='expired').count(),
                
                'today_subscriptions': subscriptions.filter(start_date__gte=today).count(),
                'week_subscriptions': subscriptions.filter(start_date__gte=last_week).count(),
                'month_subscriptions': subscriptions.filter(start_date__gte=last_month).count(),
                
                'hotspot_subscriptions': active_subscriptions.filter(access_method='hotspot').count(),
                'pppoe_subscriptions': active_subscriptions.filter(access_method='pppoe').count(),
                
                'subscription_growth_rate': DashboardDataService.calculate_percentage_change(
                    subscriptions.filter(start_date__gte=last_week).count(),
                    subscriptions.filter(start_date__range=[last_week - timedelta(days=7), last_week]).count()
                )
            }
            
            return metrics
        except Exception as e:
            logger.error(f"Error getting subscription metrics: {e}")
            return {}

    @staticmethod
    def get_plan_categories_metrics():
        """Get metrics by plan categories."""
        try:
            categories = {}
            for plan in InternetPlan.objects.filter(active=True):
                if plan.category not in categories:
                    categories[plan.category] = {
                        'plan_count': 0,
                        'active_subscriptions': 0,
                        'total_revenue': 0,
                        'avg_price': 0
                    }
                
                categories[plan.category]['plan_count'] += 1
                categories[plan.category]['active_subscriptions'] += plan.subscriptions.filter(
                    status='active', is_active=True
                ).count()
                
                # Revenue for this plan category
                plan_revenue = TransactionLog.objects.filter(
                    subscription__internet_plan=plan,
                    status='success'
                ).aggregate(total=Sum('amount'))['total'] or 0
                
                categories[plan.category]['total_revenue'] += float(plan_revenue)
            
            # Calculate average price per category
            for category in categories:
                if categories[category]['plan_count'] > 0:
                    categories[category]['avg_price'] = categories[category]['total_revenue'] / categories[category]['active_subscriptions'] if categories[category]['active_subscriptions'] > 0 else 0
            
            return categories
        except Exception as e:
            logger.error(f"Error getting plan categories metrics: {e}")
            return {}