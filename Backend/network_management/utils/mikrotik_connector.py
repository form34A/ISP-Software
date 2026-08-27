
# """
# PRODUCTION-READY MikroTik Router Connector Utility
# Enhanced with security, external configuration, monitoring, and MySQL integration.
# """

# import os
# import logging
# import socket
# import time
# import re
# import sys
# import ssl
# import datetime
# from typing import Dict, Tuple, Optional, Any, List

# # Django imports
# try:
#     from django.conf import settings
#     from django.core.cache import cache
#     from django.db import transaction
#     from django.utils import timezone
#     DJANGO_AVAILABLE = True
# except ImportError:
#     DJANGO_AVAILABLE = False
#     # Fallback implementations
#     timezone = datetime.datetime
#     class SimpleCache:
#         def get(self, key, default=None): return default
#         def set(self, key, value, timeout=None): pass
#         def delete(self, key): pass
#     cache = SimpleCache()
#     settings = type('Settings', (), {})()
#     transaction = type('Transaction', (), {'atomic': lambda: type('Context', (), {'__enter__': lambda self: None, '__exit__': lambda self, *args: None})()})()

# # RouterOS API imports
# try:
#     from routeros_api import RouterOsApiPool
#     from routeros_api.exceptions import RouterOsApiConnectionError, RouterOsApiCommunicationError
#     ROUTEROS_AVAILABLE = True
# except ImportError:
#     ROUTEROS_AVAILABLE = False
#     class RouterOsApiPool:
#         def __init__(self, *args, **kwargs):
#             raise ImportError("routeros-api package not installed")
#         def get_api(self): pass
#         def disconnect(self): pass
#         @property
#         def active_count(self): return 0
#     RouterOsApiConnectionError = RouterOsApiCommunicationError = Exception

# logger = logging.getLogger(__name__)


# class SecurityConfig:
#     """Security configuration management with proper certificate handling."""
    
#     @staticmethod
#     def get_ssl_context():
#         """Create SSL context with proper certificate verification."""
#         context = ssl.create_default_context()
        
#         # Get SSL configuration from settings
#         ssl_verify = settings.MIKROTIK_CONFIG['CONNECTION'].get('SSL_VERIFY', True)
        
#         if ssl_verify:
#             # Production: Verify certificates
#             ca_cert_path = settings.MIKROTIK_CONFIG['CONNECTION'].get('SSL_CA_CERT_PATH')
                
#             if ca_cert_path and os.path.exists(ca_cert_path):
#                 context.load_verify_locations(ca_cert_path)
#             context.verify_mode = ssl.CERT_REQUIRED
#         else:
#             # Development: Allow self-signed certificates with warning
#             logger.warning("SSL verification disabled - not recommended for production")
#             context.check_hostname = False
#             context.verify_mode = ssl.CERT_NONE
            
#         return context
    
#     @staticmethod
#     def validate_credentials(ip: str, username: str, password: str) -> Tuple[bool, List[str]]:
#         """Validate credentials before connection attempts."""
#         errors = []
        
#         # Security validation from settings
#         security_config = settings.MIKROTIK_CONFIG.get('SECURITY', {})
#         validate_credentials = security_config.get('VALIDATE_CREDENTIALS', True)
#         reject_default_passwords = security_config.get('REJECT_DEFAULT_PASSWORDS', True)
        
#         if not validate_credentials:
#             return True, errors
            
#         # Check for default credentials
#         if reject_default_passwords and username == 'admin' and password in ['', 'admin']:
#             errors.append("Default credentials detected - change for security")
            
#         # Check password strength
#         if len(password) < 8:
#             errors.append("Password too short - minimum 8 characters required")
            
#         # Check IP format
#         if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
#             errors.append("Invalid IP address format")
            
#         return len(errors) == 0, errors


# class MikroTikConfig:
#     """Externalized configuration management using Django settings."""
    
#     @classmethod
#     def get_connection_config(cls) -> Dict:
#         """Get connection configuration from settings."""
#         return settings.MIKROTIK_CONFIG['CONNECTION']
    
#     @classmethod
#     def get_pool_config(cls) -> Dict:
#         """Get pool configuration from settings."""
#         return settings.MIKROTIK_CONFIG['POOL']
    
#     @classmethod
#     def get_monitoring_config(cls) -> Dict:
#         """Get monitoring configuration from settings."""
#         return settings.MIKROTIK_CONFIG.get('MONITORING', {})
    
#     @classmethod
#     def get_logging_config(cls) -> Dict:
#         """Get logging configuration from settings."""
#         return settings.MIKROTIK_CONFIG.get('LOGGING', {})
    
#     @classmethod
#     def get_hotspot_defaults(cls):
#         """Get hotspot configuration defaults from settings."""
#         hotspot_config = settings.MIKROTIK_CONFIG['HOTSPOT']
#         return {
#             'ip_pool': hotspot_config.get('IP_POOL', '192.168.100.10-192.168.100.200'),
#             'bandwidth_limit': hotspot_config.get('BANDWIDTH_LIMIT', '10M/10M'),
#             'session_timeout': hotspot_config.get('SESSION_TIMEOUT', 60),
#             'max_users': hotspot_config.get('MAX_USERS', 50),
#             'default_ssid': hotspot_config.get('DEFAULT_SSID', 'SurfZone-WiFi'),
#         }
    
#     @classmethod
#     def get_pppoe_defaults(cls):
#         """Get PPPoE configuration defaults from settings."""
#         pppoe_config = settings.MIKROTIK_CONFIG['PPPOE']
#         return {
#             'ip_pool_name': pppoe_config.get('IP_POOL_NAME', 'pppoe-pool'),
#             'ip_range': pppoe_config.get('IP_RANGE', '192.168.101.10-192.168.101.200'),
#             'bandwidth_limit': pppoe_config.get('BANDWIDTH_LIMIT', '10M/10M'),
#             'mtu': pppoe_config.get('MTU', 1492),
#             'service_name': pppoe_config.get('SERVICE_NAME', 'PPPoE-Service'),
#         }


# class MonitoringManager:
#     """Monitoring and alerting management."""
    
#     @staticmethod
#     def record_connection_attempt(router_ip: str, success: bool):
#         """Record connection attempt metrics."""
#         monitoring_config = MikroTikConfig.get_monitoring_config()
#         if not monitoring_config.get('ENABLED', True):
#             return
            
#         status = 'success' if success else 'failure'
#         logger.info(f"Connection attempt to {router_ip}: {status}")
    
#     @staticmethod
#     def record_configuration_attempt(router_ip: str, config_type: str, success: bool):
#         """Record configuration attempt metrics."""
#         monitoring_config = MikroTikConfig.get_monitoring_config()
#         if not monitoring_config.get('ENABLED', True):
#             return
            
#         status = 'success' if success else 'failure'
#         logger.info(f"Configuration attempt {config_type} on {router_ip}: {status}")
    
#     @staticmethod
#     def record_response_time(router_ip: str, operation: str, duration: float):
#         """Record response time metrics."""
#         monitoring_config = MikroTikConfig.get_monitoring_config()
#         if not monitoring_config.get('ENABLED', True):
#             return
            
#         max_response_time = monitoring_config.get('MAX_RESPONSE_TIME_ALERT', 5.0)
#         if duration > max_response_time:
#             logger.warning(f"High response time for {operation} on {router_ip}: {duration:.2f}s")
    
#     @staticmethod
#     def check_performance_thresholds(router, response_time: float, success: bool):
#         """Check performance thresholds and create alerts."""
#         if not DJANGO_AVAILABLE:
#             return
            
#         monitoring_config = MikroTikConfig.get_monitoring_config()
#         max_response_time = monitoring_config.get('MAX_RESPONSE_TIME_ALERT', 5.0)
        
#         if response_time > max_response_time:
#             MonitoringManager._create_performance_alert(
#                 router, 
#                 f"High response time: {response_time:.2f}s (threshold: {max_response_time}s)"
#             )
        
#         if not success:
#             MonitoringManager._create_connection_alert(router, "Connection failed")
    
#     @staticmethod
#     def _create_performance_alert(router, message: str):
#         """Create performance alert in database."""
#         try:
#             # Import models here to avoid circular imports
#             from network_management.models.router_management_model import RouterHealthCheck
#             RouterHealthCheck.objects.create(
#                 router=router,
#                 is_online=True,
#                 response_time=None,
#                 error_message=message,
#                 health_score=60,
#                 critical_alerts=[message],
#                 performance_metrics={'high_response_time': True}
#             )
#             logger.warning(f"Performance alert for {router.ip}: {message}")
#         except Exception as e:
#             logger.error(f"Failed to create performance alert: {str(e)}")
    
#     @staticmethod
#     def _create_connection_alert(router, message: str):
#         """Create connection alert in database."""
#         try:
#             # Import models here to avoid circular imports
#             from network_management.models.router_management_model import RouterHealthCheck
#             RouterHealthCheck.objects.create(
#                 router=router,
#                 is_online=False,
#                 response_time=None,
#                 error_message=message,
#                 health_score=0,
#                 critical_alerts=[message],
#                 performance_metrics={}
#             )
#             logger.warning(f"Connection alert for {router.ip}: {message}")
#         except Exception as e:
#             logger.error(f"Failed to create connection alert: {str(e)}")


# class ConnectionPoolManager:
#     """
#     Enhanced connection pooling manager with security and monitoring.
#     """
    
#     _pools = {}
    
#     @classmethod
#     def get_pool(cls, ip: str, username: str, password: str, port: int = None, 
#                  router_id: int = None) -> Any:
#         """Get or create a secure connection pool for a router."""
#         if not ROUTEROS_AVAILABLE:
#             raise ImportError("routeros-api package is required for MikroTik connections")
        
#         # Security validation
#         is_valid, errors = SecurityConfig.validate_credentials(ip, username, password)
#         if not is_valid:
#             logger.warning(f"Security validation failed for {ip}: {', '.join(errors)}")
        
#         connection_config = MikroTikConfig.get_connection_config()
#         pool_config = MikroTikConfig.get_pool_config()
        
#         port = port or connection_config.get('PORT', 8728)
#         pool_key = f"{ip}:{port}:{username}"
        
#         # Clean up old pools periodically
#         cls._cleanup_old_pools()
        
#         if pool_key not in cls._pools:
#             try:
#                 use_ssl = connection_config.get('USE_SSL', False)
#                 ssl_verify = connection_config.get('SSL_VERIFY', True)
                
#                 pool = RouterOsApiPool(
#                     host=ip,
#                     username=username,
#                     password=password,
#                     port=port,
#                     plaintext_login=True,
#                     use_ssl=use_ssl,
#                     ssl_verify=ssl_verify,
#                     timeout=connection_config.get('TIMEOUT', 10),
#                     max_connections=pool_config.get('MAX_CONNECTIONS', 5)
#                 )
                
#                 cls._pools[pool_key] = {
#                     'pool': pool,
#                     'last_used': time.time(),
#                     'use_count': 0,
#                     'created_at': time.time(),
#                     'router_id': router_id
#                 }
                
#                 logger.info(f"Created new secure connection pool for {ip}:{port}")
                
#             except Exception as e:
#                 logger.error(f"Failed to create connection pool for {ip}:{port}: {str(e)}")
#                 MonitoringManager.record_connection_attempt(ip, False)
#                 raise
        
#         cls._pools[pool_key]['last_used'] = time.time()
#         cls._pools[pool_key]['use_count'] += 1
        
#         return cls._pools[pool_key]['pool']
    
#     @classmethod
#     def _cleanup_old_pools(cls):
#         """Clean up pools that haven't been used recently."""
#         current_time = time.time()
#         pool_config = MikroTikConfig.get_pool_config()
#         cleanup_interval = pool_config.get('CLEANUP_INTERVAL', 300)
#         pools_to_remove = []
        
#         for pool_key, pool_info in cls._pools.items():
#             if current_time - pool_info['last_used'] > cleanup_interval:
#                 try:
#                     pool_info['pool'].disconnect()
#                     pools_to_remove.append(pool_key)
#                     logger.info(f"Cleaned up unused connection pool: {pool_key}")
#                 except Exception as e:
#                     logger.warning(f"Error cleaning up pool {pool_key}: {str(e)}")
        
#         for pool_key in pools_to_remove:
#             del cls._pools[pool_key]
    
#     @classmethod
#     def get_pool_stats(cls) -> Dict:
#         """Get statistics about connection pools."""
#         return {
#             'total_pools': len(cls._pools),
#             'pools': {
#                 key: {
#                     'use_count': info['use_count'],
#                     'last_used': info['last_used'],
#                     'created_at': info['created_at'],
#                     'router_id': info.get('router_id')
#                 } for key, info in cls._pools.items()
#             }
#         }
    
#     @classmethod
#     def disconnect_pool(cls, ip: str, port: int = None, username: str = None):
#         """Disconnect specific pool."""
#         connection_config = MikroTikConfig.get_connection_config()
#         port = port or connection_config.get('PORT', 8728)
        
#         if username:
#             pool_key = f"{ip}:{port}:{username}"
#         else:
#             # Find by IP and port only
#             pool_key = next((k for k in cls._pools.keys() if k.startswith(f"{ip}:{port}:")), None)
        
#         if pool_key and pool_key in cls._pools:
#             try:
#                 cls._pools[pool_key]['pool'].disconnect()
#                 del cls._pools[pool_key]
#                 logger.info(f"Disconnected pool: {pool_key}")
#             except Exception as e:
#                 logger.error(f"Error disconnecting pool {pool_key}: {str(e)}")
    
#     @classmethod
#     def disconnect_all_pools(cls):
#         """Disconnect all connection pools."""
#         pools_to_remove = list(cls._pools.keys())
#         for pool_key in pools_to_remove:
#             try:
#                 cls._pools[pool_key]['pool'].disconnect()
#                 del cls._pools[pool_key]
#                 logger.info(f"Disconnected pool: {pool_key}")
#             except Exception as e:
#                 logger.error(f"Error disconnecting pool {pool_key}: {str(e)}")
        
#         logger.info("All connection pools disconnected")


# class DatabaseManager:
#     """MySQL database operations manager."""
    
#     @staticmethod
#     def save_connection_test(router, test_results: Dict, user=None):
#         """Save connection test results to database."""
#         if not DJANGO_AVAILABLE:
#             return None
            
#         logging_config = MikroTikConfig.get_logging_config()
#         if not logging_config.get('SAVE_CONNECTION_TESTS', True):
#             return None
            
#         try:
#             # Import models here to avoid circular imports
#             from network_management.models.router_management_model import RouterConnectionTest
            
#             with transaction.atomic():
#                 connection_test = RouterConnectionTest.objects.create(
#                     router=router,
#                     success=test_results.get('system_access', False),
#                     response_time=test_results.get('response_time'),
#                     system_info=test_results.get('system_info', {}),
#                     error_messages=test_results.get('error_messages', []),
#                     tested_by=user
#                 )
                
#                 # Update router status
#                 router.connection_status = 'connected' if test_results.get('system_access') else 'disconnected'
#                 router.last_connection_test = timezone.now()
                
#                 if test_results.get('system_info'):
#                     router.firmware_version = test_results['system_info'].get('version', router.firmware_version)
                
#                 router.save()
                
#                 return connection_test
                
#         except Exception as e:
#             logger.error(f"Failed to save connection test for router {router.id}: {str(e)}")
#             return None
    
#     @staticmethod
#     def create_audit_log(router, action: str, description: str, 
#                         user=None, ip_address: str = None, changes: Dict = None):
#         """Create audit log entry."""
#         if not DJANGO_AVAILABLE:
#             return
            
#         try:
#             # Import models here to avoid circular imports
#             from network_management.models.router_management_model import RouterAuditLog
#             RouterAuditLog.objects.create(
#                 router=router,
#                 action=action,
#                 description=description,
#                 user=user,
#                 ip_address=ip_address,
#                 changes=changes or {}
#             )
#         except Exception as e:
#             logger.error(f"Failed to create audit log: {str(e)}")
    
#     @staticmethod
#     def update_router_configuration_status(router, config_type: str, success: bool, 
#                                          errors: List[str] = None):
#         """Update router configuration status."""
#         if not DJANGO_AVAILABLE:
#             return
            
#         try:
#             if success:
#                 if router.configuration_status == 'not_configured':
#                     router.configuration_status = 'configured'
#                 elif router.configuration_status == 'partially_configured':
#                     router.configuration_status = 'configured'
#                 router.configuration_type = config_type
#             else:
#                 if router.configuration_status == 'configured':
#                     router.configuration_status = 'partially_configured'
#                 else:
#                     router.configuration_status = 'configuration_failed'
            
#             router.last_configuration_update = timezone.now()
#             router.save()
            
#         except Exception as e:
#             logger.error(f"Failed to update router configuration status: {str(e)}")


# class MikroTikConnector:
#     """
#     PRODUCTION-READY MikroTik router connection and configuration manager.
#     Enhanced with security, monitoring, and database integration.
#     """
    
#     def __init__(self, ip: str, username: str, password: str, port: int = None, 
#                  timeout: int = None, max_retries: int = None, use_ssl: bool = None,
#                  router_id: int = None):
#         self.ip = ip
#         self.username = username
#         self.password = password
        
#         # Get configuration from settings
#         connection_config = MikroTikConfig.get_connection_config()
#         self.port = port or connection_config.get('PORT', 8728)
#         self.timeout = timeout or connection_config.get('TIMEOUT', 10)
#         self.max_retries = max_retries or connection_config.get('MAX_RETRIES', 3)
#         self.use_ssl = use_ssl if use_ssl is not None else connection_config.get('USE_SSL', False)
#         self.router_id = router_id
        
#         self.api_pool = None
#         self.api = None
        
#         # Validate parameters
#         self._validate_parameters()
    
#     def _validate_parameters(self):
#         """Validate connection parameters with security checks."""
#         if not self.ip or not self.username:
#             raise ValueError("IP address and username are required")
        
#         if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', self.ip):
#             raise ValueError("Invalid IP address format")
        
#         if not (1 <= self.port <= 65535):
#             raise ValueError("Port must be between 1 and 65535")
        
#         # Security validation
#         is_valid, errors = SecurityConfig.validate_credentials(self.ip, self.username, self.password)
#         if not is_valid:
#             logger.warning(f"Security issues detected: {', '.join(errors)}")
    
#     def connect(self, user=None) -> Tuple[bool, str, Any]:
#         """
#         Enhanced secure connection establishment with monitoring and database logging.
#         """
#         pool_config = MikroTikConfig.get_pool_config()
#         cache_key = f"router_connection:{self.ip}:{self.port}"
#         cached_result = cache.get(cache_key)
        
#         # Check cached connection
#         if cached_result and cached_result.get('status') == 'connected':
#             cache_age = time.time() - cached_result.get('timestamp', 0)
#             cache_timeout = pool_config.get('CACHE_TIMEOUT', 300)
#             if cache_age < cache_timeout:
#                 logger.debug(f"Using cached connection for {self.ip}")
#                 return True, "Connection verified from cache", cached_result.get('api_data')
        
#         start_time = time.time()
        
#         # Attempt connection with retries
#         for attempt in range(self.max_retries):
#             try:
#                 # Test basic connectivity first
#                 if not self._test_connectivity():
#                     wait_time = 2 ** attempt  # Exponential backoff
#                     logger.warning(f"Connectivity test failed for {self.ip}, attempt {attempt + 1}. Retrying in {wait_time}s")
#                     time.sleep(wait_time)
#                     continue
                
#                 # Use secure connection pool
#                 self.api_pool = ConnectionPoolManager.get_pool(
#                     self.ip, self.username, self.password, self.port, self.router_id
#                 )
                
#                 self.api = self.api_pool.get_api()
                
#                 # Verify connection by fetching system info
#                 system_resource = self.api.get_resource('/system/resource')
#                 system_info = system_resource.get()
                
#                 if not system_info:
#                     logger.warning(f"No system info received from {self.ip}, attempt {attempt + 1}")
#                     continue
                
#                 # Cache successful connection
#                 connection_data = {
#                     'status': 'connected',
#                     'system_info': system_info[0],
#                     'timestamp': time.time(),
#                     'api_data': self.api
#                 }
#                 cache.set(cache_key, connection_data, pool_config.get('CACHE_TIMEOUT', 300))
                
#                 response_time = time.time() - start_time
                
#                 # Record metrics
#                 MonitoringManager.record_connection_attempt(self.ip, True)
#                 MonitoringManager.record_response_time(self.ip, 'connect', response_time)
                
#                 logger.info(f"Successfully connected to MikroTik router at {self.ip} (attempt {attempt + 1}, response time: {response_time:.2f}s)")
#                 return True, "Connection established successfully", self.api
                
#             except RouterOsApiConnectionError as e:
#                 error_msg = f"Connection failed (attempt {attempt + 1}): {str(e)}"
#                 logger.warning(f"MikroTik connection error for {self.ip}: {error_msg}")
#                 MonitoringManager.record_connection_attempt(self.ip, False)
                
#                 if attempt == self.max_retries - 1:
#                     return False, error_msg, None
#                 time.sleep(2 ** attempt)
                
#             except RouterOsApiCommunicationError as e:
#                 error_msg = f"Authentication failed (attempt {attempt + 1}): {str(e)}"
#                 logger.error(f"MikroTik authentication error for {self.ip}: {error_msg}")
#                 MonitoringManager.record_connection_attempt(self.ip, False)
#                 return False, error_msg, None
                
#             except Exception as e:
#                 error_msg = f"Unexpected error (attempt {attempt + 1}): {str(e)}"
#                 logger.error(f"MikroTik unexpected error for {self.ip}: {error_msg}")
#                 MonitoringManager.record_connection_attempt(self.ip, False)
                
#                 if attempt == self.max_retries - 1:
#                     return False, error_msg, None
#                 time.sleep(2 ** attempt)
        
#         return False, "All connection attempts failed", None
    
#     def _test_connectivity(self) -> bool:
#         """Enhanced network connectivity test with timeout."""
#         try:
#             sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#             sock.settimeout(self.timeout)
#             result = sock.connect_ex((self.ip, self.port))
#             sock.close()
            
#             if result == 0:
#                 logger.debug(f"Connectivity test passed for {self.ip}:{self.port}")
#                 return True
#             else:
#                 logger.warning(f"Connectivity test failed for {self.ip}:{self.port} (error code: {result})")
#                 return False
                
#         except Exception as e:
#             logger.error(f"Connectivity test exception for {self.ip}:{self.port}: {str(e)}")
#             return False
    
#     def test_connection(self, user=None) -> Dict[str, Any]:
#         """
#         Comprehensive connection test with monitoring and database storage.
#         """
#         if not ROUTEROS_AVAILABLE:
#             test_results = {
#                 'ip': self.ip,
#                 'port': self.port,
#                 'timestamp': self._get_current_timestamp(),
#                 'basic_connectivity': False,
#                 'api_connection': False,
#                 'authentication': False,
#                 'system_access': False,
#                 'response_time': None,
#                 'system_info': {},
#                 'error_messages': ['routeros-api package not installed'],
#                 'attempts_made': 0,
#                 'capabilities': {}
#             }
            
#             # Still save to database even if connector not available
#             if self.router_id and DJANGO_AVAILABLE:
#                 try:
#                     # Import models here to avoid circular imports
#                     from network_management.models.router_management_model import Router
#                     router = Router.objects.get(id=self.router_id)
#                     DatabaseManager.save_connection_test(router, test_results, user)
#                 except Exception as e:
#                     logger.warning(f"Failed to save connection test for router {self.router_id}: {str(e)}")
                    
#             return test_results
        
#         start_time = time.time()
        
#         test_results = {
#             'ip': self.ip,
#             'port': self.port,
#             'timestamp': self._get_current_timestamp(),
#             'basic_connectivity': False,
#             'api_connection': False,
#             'authentication': False,
#             'system_access': False,
#             'response_time': None,
#             'system_info': {},
#             'capabilities': {},
#             'error_messages': [],
#             'attempts_made': 0,
#             'recommendations': []
#         }
        
#         for attempt in range(self.max_retries):
#             test_results['attempts_made'] = attempt + 1
            
#             try:
#                 # Test 1: Basic network connectivity
#                 test_results['basic_connectivity'] = self._test_connectivity()
#                 if not test_results['basic_connectivity']:
#                     error_msg = f"Attempt {attempt + 1}: Network connectivity test failed"
#                     test_results['error_messages'].append(error_msg)
#                     test_results['recommendations'].append("Check network connectivity and firewall rules")
#                     if attempt < self.max_retries - 1:
#                         time.sleep(1)
#                         continue
#                     break
                
#                 # Test 2: API Connection and Authentication
#                 success, message, api = self.connect(user)
                
#                 if not success:
#                     test_results['error_messages'].append(f"Attempt {attempt + 1}: {message}")
#                     if attempt < self.max_retries - 1:
#                         time.sleep(2 ** attempt)
#                         continue
#                     break
                
#                 test_results['api_connection'] = True
#                 test_results['authentication'] = True
                
#                 # Test 3: System access and information retrieval
#                 try:
#                     system_resource = api.get_resource('/system/resource')
#                     system_info = system_resource.get()
                    
#                     if system_info:
#                         test_results['system_access'] = True
#                         test_results['system_info'] = self._extract_system_info(system_info[0])
#                         test_results['capabilities'] = self._determine_capabilities(system_info[0])
                        
#                         # Get additional router information
#                         self._get_additional_router_info(api, test_results)
                    
#                     # Calculate response time
#                     end_time = time.time()
#                     test_results['response_time'] = end_time - start_time
                    
#                     # Generate recommendations
#                     self._generate_recommendations(test_results)
                    
#                     break  # Success, exit retry loop
                    
#                 except Exception as e:
#                     error_msg = f"Attempt {attempt + 1}: System access failed: {str(e)}"
#                     test_results['error_messages'].append(error_msg)
#                     if attempt < self.max_retries - 1:
#                         time.sleep(2 ** attempt)
#                         continue
                
#             except Exception as e:
#                 error_msg = f"Attempt {attempt + 1}: Unexpected error: {str(e)}"
#                 test_results['error_messages'].append(error_msg)
#                 if attempt < self.max_retries - 1:
#                     time.sleep(2 ** attempt)
#                     continue
        
#         # Cleanup
#         if self.api_pool:
#             try:
#                 self.api_pool.disconnect()
#             except Exception as e:
#                 logger.warning(f"Error disconnecting pool during test: {str(e)}")
        
#         # Save to database
#         if self.router_id and DJANGO_AVAILABLE:
#             try:
#                 # Import models here to avoid circular imports
#                 from network_management.models.router_management_model import Router
#                 router = Router.objects.get(id=self.router_id)
#                 DatabaseManager.save_connection_test(router, test_results, user)
                
#                 # Performance monitoring
#                 MonitoringManager.check_performance_thresholds(
#                     router, 
#                     test_results.get('response_time', 0),
#                     test_results.get('system_access', False)
#                 )
                
#             except Exception as e:
#                 logger.warning(f"Router with ID {self.router_id} not found for connection test: {str(e)}")
        
#         return test_results

#     def _get_current_timestamp(self):
#         """Get current timestamp in ISO format."""
#         if DJANGO_AVAILABLE:
#             return timezone.now().isoformat()
#         else:
#             return datetime.datetime.now().isoformat()
    
#     def configure_hotspot(self, ssid: str = None, welcome_message: str = None, bandwidth_limit: str = None, 
#                          session_timeout: int = None, max_users: int = None, redirect_url: str = None,
#                          ip_pool: str = None, user=None) -> Tuple[bool, str, Dict]:
#         """
#         Enhanced hotspot configuration with security, monitoring, and database integration.
#         """
#         start_time = time.time()
        
#         # Use configured defaults
#         defaults = MikroTikConfig.get_hotspot_defaults()
#         ssid = ssid or defaults['default_ssid']
#         bandwidth_limit = bandwidth_limit or defaults['bandwidth_limit']
#         session_timeout = session_timeout or defaults['session_timeout']
#         max_users = max_users or defaults['max_users']
#         ip_pool = ip_pool or defaults['ip_pool']
        
#         try:
#             success, message, api = self.connect(user)
#             if not success:
#                 MonitoringManager.record_configuration_attempt(self.ip, 'hotspot', False)
#                 return False, message, {}
            
#             configuration_steps = []
#             config_details = {
#                 'ssid': ssid,
#                 'bandwidth_limit': bandwidth_limit,
#                 'session_timeout': session_timeout,
#                 'max_users': max_users,
#                 'steps_completed': [],
#                 'failed_steps': []
#             }
            
#             # Validate parameters
#             validation_errors = self._validate_hotspot_parameters(ssid, bandwidth_limit, session_timeout, max_users)
#             if validation_errors:
#                 MonitoringManager.record_configuration_attempt(self.ip, 'hotspot', False)
#                 return False, f"Parameter validation failed: {', '.join(validation_errors)}", config_details
            
#             try:
#                 # Step 1: Configure IP pool
#                 pool_step = self._configure_ip_pool(api, 'hotspot-pool', ip_pool)
#                 configuration_steps.append(pool_step)
                
#                 # Step 2: Configure wireless interface
#                 wireless_step = self._configure_wireless_interface(api, ssid)
#                 configuration_steps.append(wireless_step)
                
#                 # Step 3: Configure hotspot server
#                 hotspot_step = self._configure_hotspot_server(api, ssid, redirect_url)
#                 configuration_steps.append(hotspot_step)
                
#                 # Step 4: Configure hotspot profile
#                 profile_step = self._configure_hotspot_profile(
#                     api, bandwidth_limit, session_timeout, welcome_message
#                 )
#                 configuration_steps.append(profile_step)
                
#                 # Step 5: Configure user profiles
#                 user_step = self._configure_user_profiles(api, max_users, bandwidth_limit)
#                 configuration_steps.append(user_step)
                
#                 # Step 6: Configure firewall rules
#                 firewall_step = self._configure_hotspot_firewall(api)
#                 configuration_steps.append(firewall_step)
                
#             except Exception as e:
#                 logger.error(f"Hotspot configuration steps failed: {str(e)}")
#                 MonitoringManager.record_configuration_attempt(self.ip, 'hotspot', False)
#                 return False, f"Configuration steps failed: {str(e)}", config_details
            
#             finally:
#                 # Always attempt to cleanup connection
#                 try:
#                     if self.api_pool:
#                         self.api_pool.disconnect()
#                 except Exception as e:
#                     logger.warning(f"Error during connection cleanup: {str(e)}")
            
#             # Compile results
#             for step in configuration_steps:
#                 if step['success']:
#                     config_details['steps_completed'].append(step['step'])
#                 else:
#                     config_details['failed_steps'].append({
#                         'step': step['step'],
#                         'error': step.get('error', 'Unknown error')
#                     })
            
#             config_details['configuration_steps'] = configuration_steps
            
#             failed_count = len(config_details['failed_steps'])
#             overall_success = failed_count == 0
            
#             # Record metrics
#             response_time = time.time() - start_time
#             MonitoringManager.record_configuration_attempt(self.ip, 'hotspot', overall_success)
#             MonitoringManager.record_response_time(self.ip, 'configure_hotspot', response_time)
            
#             # Update database
#             if self.router_id and DJANGO_AVAILABLE:
#                 try:
#                     # Import models here to avoid circular imports
#                     from network_management.models.router_management_model import Router
#                     router = Router.objects.get(id=self.router_id)
#                     DatabaseManager.update_router_configuration_status(
#                         router, 'hotspot', overall_success, 
#                         [step['error'] for step in config_details['failed_steps']]
#                     )
                    
#                     # Create audit log
#                     DatabaseManager.create_audit_log(
#                         router=router,
#                         action='configure',
#                         description=f"Hotspot configuration {'completed successfully' if overall_success else 'partially failed'}",
#                         user=user,
#                         changes=config_details
#                     )
                    
#                 except Exception as e:
#                     logger.warning(f"Router with ID {self.router_id} not found for configuration update: {str(e)}")
            
#             if overall_success:
#                 return True, "Hotspot configuration completed successfully", config_details
#             elif failed_count < len(configuration_steps):
#                 return False, f"Hotspot configuration partially completed ({failed_count} failures)", config_details
#             else:
#                 return False, "Hotspot configuration failed completely", config_details
                
#         except Exception as e:
#             logger.error(f"Hotspot configuration failed for {self.ip}: {str(e)}")
#             MonitoringManager.record_configuration_attempt(self.ip, 'hotspot', False)
#             return False, f"Configuration failed: {str(e)}", {}
    
#     def configure_pppoe(self, service_name: str = None, bandwidth_limit: str = None, 
#                        mtu: int = None, ip_pool_name: str = None, 
#                        ip_range: str = None, user=None) -> Tuple[bool, str, Dict]:
#         """
#         Enhanced PPPoE configuration with security, monitoring, and database integration.
#         """
#         start_time = time.time()
        
#         # Use configured defaults
#         defaults = MikroTikConfig.get_pppoe_defaults()
#         service_name = service_name or defaults.get('service_name', 'PPPoE-Service')
#         bandwidth_limit = bandwidth_limit or defaults['bandwidth_limit']
#         mtu = mtu or defaults['mtu']
#         ip_pool_name = ip_pool_name or defaults['ip_pool_name']
#         ip_range = ip_range or defaults['ip_range']
        
#         try:
#             success, message, api = self.connect(user)
#             if not success:
#                 MonitoringManager.record_configuration_attempt(self.ip, 'pppoe', False)
#                 return False, message, {}
            
#             configuration_steps = []
#             config_details = {
#                 'service_name': service_name,
#                 'bandwidth_limit': bandwidth_limit,
#                 'mtu': mtu,
#                 'ip_pool_name': ip_pool_name,
#                 'steps_completed': [],
#                 'failed_steps': []
#             }
            
#             try:
#                 # Step 1: Configure IP pool for PPPoE
#                 pool_step = self._configure_ip_pool(api, ip_pool_name, ip_range)
#                 configuration_steps.append(pool_step)
                
#                 # Step 2: Configure PPPoE server
#                 pppoe_step = self._configure_pppoe_server(api, service_name, mtu)
#                 configuration_steps.append(pppoe_step)
                
#                 # Step 3: Configure PPP profiles
#                 profile_step = self._configure_ppp_profiles(api, bandwidth_limit, ip_pool_name)
#                 configuration_steps.append(profile_step)
                
#                 # Step 4: Configure PPPoE secrets (example user)
#                 secret_step = self._configure_pppoe_secrets(api)
#                 configuration_steps.append(secret_step)
                
#             except Exception as e:
#                 logger.error(f"PPPoE configuration steps failed: {str(e)}")
#                 MonitoringManager.record_configuration_attempt(self.ip, 'pppoe', False)
#                 return False, f"Configuration steps failed: {str(e)}", config_details
            
#             finally:
#                 try:
#                     if self.api_pool:
#                         self.api_pool.disconnect()
#                 except Exception as e:
#                     logger.warning(f"Error during connection cleanup: {str(e)}")
            
#             # Compile results
#             for step in configuration_steps:
#                 if step['success']:
#                     config_details['steps_completed'].append(step['step'])
#                 else:
#                     config_details['failed_steps'].append({
#                         'step': step['step'],
#                         'error': step.get('error', 'Unknown error')
#                     })
            
#             config_details['configuration_steps'] = configuration_steps
            
#             failed_count = len(config_details['failed_steps'])
#             overall_success = failed_count == 0
            
#             # Record metrics
#             response_time = time.time() - start_time
#             MonitoringManager.record_configuration_attempt(self.ip, 'pppoe', overall_success)
#             MonitoringManager.record_response_time(self.ip, 'configure_pppoe', response_time)
            
#             # Update database
#             if self.router_id and DJANGO_AVAILABLE:
#                 try:
#                     # Import models here to avoid circular imports
#                     from network_management.models.router_management_model import Router
#                     router = Router.objects.get(id=self.router_id)
#                     DatabaseManager.update_router_configuration_status(
#                         router, 'pppoe', overall_success,
#                         [step['error'] for step in config_details['failed_steps']]
#                     )
                    
#                     # Create audit log
#                     DatabaseManager.create_audit_log(
#                         router=router,
#                         action='configure',
#                         description=f"PPPoE configuration {'completed successfully' if overall_success else 'partially failed'}",
#                         user=user,
#                         changes=config_details
#                     )
                    
#                 except Exception as e:
#                     logger.warning(f"Router with ID {self.router_id} not found for configuration update: {str(e)}")
            
#             if overall_success:
#                 return True, "PPPoE configuration completed successfully", config_details
#             elif failed_count < len(configuration_steps):
#                 return False, f"PPPoE configuration partially completed ({failed_count} failures)", config_details
#             else:
#                 return False, "PPPoE configuration failed completely", config_details
                
#         except Exception as e:
#             logger.error(f"PPPoE configuration failed for {self.ip}: {str(e)}")
#             MonitoringManager.record_configuration_attempt(self.ip, 'pppoe', False)
#             return False, f"Configuration failed: {str(e)}", {}
    
#     # Configuration helper methods (these remain the same as in original)
#     def _configure_ip_pool(self, api, pool_name: str, ip_range: str) -> Dict:
#         """Configure IP pool."""
#         try:
#             ip_pool = api.get_resource('/ip/pool')
#             existing_pools = ip_pool.get(name=pool_name)
            
#             if existing_pools:
#                 ip_pool.set(id=existing_pools[0].get('.id'), ranges=ip_range)
#                 return {'step': 'ip_pool', 'success': True, 'action': 'updated', 'pool_name': pool_name}
#             else:
#                 ip_pool.add(name=pool_name, ranges=ip_range)
#                 return {'step': 'ip_pool', 'success': True, 'action': 'created', 'pool_name': pool_name}
                
#         except Exception as e:
#             logger.error(f"IP pool configuration failed: {str(e)}")
#             return {'step': 'ip_pool', 'success': False, 'error': str(e)}
    
#     def _configure_wireless_interface(self, api, ssid: str) -> Dict:
#         """Configure wireless interface."""
#         try:
#             wireless = api.get_resource('/interface/wireless')
#             interfaces = wireless.get()
            
#             if interfaces:
#                 wireless.set(
#                     id=interfaces[0].get('.id'),
#                     ssid=ssid,
#                     disabled='no'
#                 )
#                 return {'step': 'wireless_interface', 'success': True, 'action': 'updated', 'ssid': ssid}
#             else:
#                 wireless.add(
#                     name="wlan1",
#                     ssid=ssid,
#                     mode="ap-bridge",
#                     band="2ghz-b/g/n",
#                     disabled='no'
#                 )
#                 return {'step': 'wireless_interface', 'success': True, 'action': 'created', 'ssid': ssid}
                
#         except Exception as e:
#             logger.error(f"Wireless interface configuration failed: {str(e)}")
#             return {'step': 'wireless_interface', 'success': False, 'error': str(e)}
    
#     def _configure_hotspot_server(self, api, ssid: str, redirect_url: str = None) -> Dict:
#         """Configure hotspot server."""
#         try:
#             hotspot = api.get_resource('/ip/hotspot')
#             servers = hotspot.get()
            
#             hotspot_server_config = {
#                 'name': ssid,
#                 'interface': 'bridge',
#                 'address-pool': 'hotspot-pool',
#                 'profile': 'default',
#                 'disabled': 'no'
#             }
            
#             if redirect_url:
#                 hotspot_server_config['login-by'] = 'http-chap'
            
#             if servers:
#                 hotspot.set(id=servers[0].get('.id'), **hotspot_server_config)
#                 return {'step': 'hotspot_server', 'success': True, 'action': 'updated'}
#             else:
#                 hotspot.add(**hotspot_server_config)
#                 return {'step': 'hotspot_server', 'success': True, 'action': 'created'}
                
#         except Exception as e:
#             logger.error(f"Hotspot server configuration failed: {str(e)}")
#             return {'step': 'hotspot_server', 'success': False, 'error': str(e)}
    
#     def _configure_hotspot_profile(self, api, bandwidth_limit: str, session_timeout: int, welcome_message: str = None) -> Dict:
#         """Configure hotspot profile."""
#         try:
#             profile = api.get_resource('/ip/hotspot/profile')
#             profiles = profile.get(name='default')
            
#             profile_config = {
#                 'name': 'default',
#                 'login-by': 'mac,http-chap,trial',
#                 'rate-limit': bandwidth_limit,
#                 'session-timeout': f'{session_timeout}m'
#             }
            
#             if welcome_message:
#                 profile_config['html-directory'] = 'hotspot'
            
#             if profiles:
#                 profile.set(id=profiles[0].get('.id'), **profile_config)
#                 return {'step': 'hotspot_profile', 'success': True, 'action': 'updated'}
#             else:
#                 profile.add(**profile_config)
#                 return {'step': 'hotspot_profile', 'success': True, 'action': 'created'}
                
#         except Exception as e:
#             logger.error(f"Hotspot profile configuration failed: {str(e)}")
#             return {'step': 'hotspot_profile', 'success': False, 'error': str(e)}
    
#     def _configure_user_profiles(self, api, max_users: int, bandwidth_limit: str) -> Dict:
#         """Configure user profiles."""
#         try:
#             user_profile = api.get_resource('/ip/hotspot/user/profile')
#             default_profile = user_profile.get(name='default')
            
#             profile_config = {
#                 'name': 'default',
#                 'rate-limit': bandwidth_limit,
#                 'shared-users': str(max_users)
#             }
            
#             if default_profile:
#                 user_profile.set(id=default_profile[0].get('.id'), **profile_config)
#             else:
#                 user_profile.add(**profile_config)
                
#             return {'step': 'user_profiles', 'success': True, 'action': 'configured'}
            
#         except Exception as e:
#             logger.error(f"User profiles configuration failed: {str(e)}")
#             return {'step': 'user_profiles', 'success': False, 'error': str(e)}
    
#     def _configure_hotspot_firewall(self, api) -> Dict:
#         """Configure basic firewall rules for hotspot."""
#         try:
#             firewall = api.get_resource('/ip/firewall/filter')
            
#             rules = [
#                 {
#                     'chain': 'input',
#                     'protocol': 'tcp',
#                     'dst-port': '80,443',
#                     'action': 'accept',
#                     'comment': 'Hotspot HTTP/HTTPS'
#                 },
#                 {
#                     'chain': 'input', 
#                     'protocol': 'udp',
#                     'dst-port': '53',
#                     'action': 'accept',
#                     'comment': 'Hotspot DNS'
#                 }
#             ]
            
#             for rule in rules:
#                 firewall.add(**rule)
            
#             return {'step': 'hotspot_firewall', 'success': True, 'action': 'configured'}
            
#         except Exception as e:
#             logger.error(f"Hotspot firewall configuration failed: {str(e)}")
#             return {'step': 'hotspot_firewall', 'success': False, 'error': str(e)}
    
#     def _configure_pppoe_server(self, api, service_name: str, mtu: int) -> Dict:
#         """Configure PPPoE server."""
#         try:
#             pppoe_server = api.get_resource('/interface/pppoe-server/server')
#             servers = pppoe_server.get()
            
#             server_config = {
#                 'service-name': service_name,
#                 'interface': 'bridge',
#                 'max-mtu': str(mtu),
#                 'max-mru': str(mtu),
#                 'disabled': 'no'
#             }
            
#             if servers:
#                 pppoe_server.set(id=servers[0].get('.id'), **server_config)
#                 return {'step': 'pppoe_server', 'success': True, 'action': 'updated'}
#             else:
#                 pppoe_server.add(**server_config)
#                 return {'step': 'pppoe_server', 'success': True, 'action': 'created'}
                
#         except Exception as e:
#             logger.error(f"PPPoE server configuration failed: {str(e)}")
#             return {'step': 'pppoe_server', 'success': False, 'error': str(e)}
    
#     def _configure_ppp_profiles(self, api, bandwidth_limit: str, ip_pool_name: str) -> Dict:
#         """Configure PPP profiles for PPPoE."""
#         try:
#             ppp_profile = api.get_resource('/ppp/profile')
#             default_profile = ppp_profile.get(name='default')
            
#             profile_config = {
#                 'name': 'default',
#                 'local-address': '192.168.101.1',
#                 'remote-address': ip_pool_name,
#                 'rate-limit': bandwidth_limit,
#                 'change-tcp-mss': 'yes'
#             }
            
#             if default_profile:
#                 ppp_profile.set(id=default_profile[0].get('.id'), **profile_config)
#             else:
#                 ppp_profile.add(**profile_config)
            
#             return {'step': 'ppp_profiles', 'success': True, 'action': 'configured'}
            
#         except Exception as e:
#             logger.error(f"PPP profiles configuration failed: {str(e)}")
#             return {'step': 'ppp_profiles', 'success': False, 'error': str(e)}
    
#     def _configure_pppoe_secrets(self, api) -> Dict:
#         """Configure example PPPoE user secrets."""
#         try:
#             ppp_secret = api.get_resource('/ppp/secret')
            
#             # Use keyword arguments to avoid positional argument error
#             ppp_secret.add(
#                 name='testuser',
#                 password='testpass123',
#                 service='pppoe',
#                 profile='default',
#                 remote_address='192.168.101.10'
#             )
            
#             return {'step': 'pppoe_secrets', 'success': True, 'action': 'created'}
            
#         except Exception as e:
#             logger.error(f"PPPoE secrets configuration failed: {str(e)}")
#             return {'step': 'pppoe_secrets', 'success': False, 'error': str(e)}
    
#     def _validate_hotspot_parameters(self, ssid: str, bandwidth_limit: str, session_timeout: int, max_users: int) -> list:
#         """Validate hotspot configuration parameters."""
#         errors = []
        
#         if not ssid or len(ssid.strip()) == 0:
#             errors.append("SSID cannot be empty")
#         elif len(ssid) > 32:
#             errors.append("SSID cannot exceed 32 characters")
        
#         if not bandwidth_limit:
#             errors.append("Bandwidth limit cannot be empty")
#         elif not re.match(r'^\d+[KM]/\d+[KM]$', bandwidth_limit):
#             errors.append("Bandwidth limit must be in format like '10M/10M'")
        
#         if session_timeout < 1 or session_timeout > 1440:
#             errors.append("Session timeout must be between 1 and 1440 minutes")
        
#         if max_users < 1 or max_users > 1000:
#             errors.append("Max users must be between 1 and 1000")
        
#         return errors
    
#     def _extract_system_info(self, system_info: Dict) -> Dict:
#         """Extract and format system information."""
#         return {
#             'model': system_info.get('board-name', 'Unknown'),
#             'version': system_info.get('version', 'Unknown'),
#             'architecture': system_info.get('architecture', 'Unknown'),
#             'cpu_load': system_info.get('cpu-load', 'Unknown'),
#             'uptime': system_info.get('uptime', 'Unknown'),
#             'free_memory': system_info.get('free-memory', 'Unknown'),
#             'total_memory': system_info.get('total-memory', 'Unknown'),
#             'cpu_count': system_info.get('cpu-count', '1'),
#             'platform': system_info.get('platform', 'Unknown')
#         }
    
#     def _determine_capabilities(self, system_info: Dict) -> Dict:
#         """Determine router capabilities based on system information."""
#         capabilities = {
#             'hotspot_support': True,
#             'pppoe_support': True,
#             'wireless_support': False,
#             'advanced_qos': False,
#             'vlan_support': True,
#             'bridge_support': True,
#             'advanced_routing': False
#         }
        
#         model = system_info.get('board-name', '').lower()
        
#         # Check for wireless capabilities
#         wireless_indicators = ['rb', 'sxt', 'lhg', 'wif', 'audience', 'cap', 'wap']
#         if any(indicator in model for indicator in wireless_indicators):
#             capabilities['wireless_support'] = True
        
#         # Check for advanced features
#         advanced_indicators = ['ccr', 'rb4011', 'rb5009', 'chateau', 'ltap', 'rb1100']
#         if any(indicator in model for indicator in advanced_indicators):
#             capabilities['advanced_qos'] = True
#             capabilities['advanced_routing'] = True
        
#         return capabilities
    
#     def _get_additional_router_info(self, api, test_results: Dict):
#         """Get additional router information."""
#         try:
#             interfaces = api.get_resource('/interface')
#             interface_list = interfaces.get()
#             test_results['interface_count'] = len(interface_list)
            
#             try:
#                 wireless = api.get_resource('/interface/wireless')
#                 wireless_list = wireless.get()
#                 test_results['wireless_interfaces'] = len(wireless_list)
#             except:
#                 test_results['wireless_interfaces'] = 0
            
#             try:
#                 hotspot_servers = api.get_resource('/ip/hotspot')
#                 test_results['hotspot_configured'] = len(hotspot_servers.get()) > 0
#             except:
#                 test_results['hotspot_configured'] = False
            
#             try:
#                 pppoe_servers = api.get_resource('/interface/pppoe-server/server')
#                 test_results['pppoe_configured'] = len(pppoe_servers.get()) > 0
#             except:
#                 test_results['pppoe_configured'] = False
                
#         except Exception as e:
#             logger.warning(f"Could not get additional router info: {str(e)}")
    
#     def _generate_recommendations(self, test_results: Dict):
#         """Generate recommendations based on test results."""
#         if not test_results['system_access']:
#             return
        
#         capabilities = test_results.get('capabilities', {})
        
#         if capabilities.get('wireless_support') and not test_results.get('hotspot_configured'):
#             test_results['recommendations'].append("Router supports wireless - consider configuring hotspot")
        
#         if capabilities.get('pppoe_support') and not test_results.get('pppoe_configured'):
#             test_results['recommendations'].append("Router supports PPPoE - consider configuring PPPoE server")
        
#         if test_results.get('response_time', 0) > 2.0:
#             test_results['recommendations'].append("High response time detected - check network latency")
    
#     def get_router_status(self) -> Dict:
#         """
#         Get comprehensive router status and statistics.
        
#         Returns:
#             dict: Router status information
#         """
#         try:
#             success, message, api = self.connect()
#             if not success:
#                 return {
#                     'online': False,
#                     'error': message,
#                     'timestamp': self._get_current_timestamp()
#                 }
            
#             status_info = {
#                 'online': True,
#                 'timestamp': self._get_current_timestamp(),
#                 'system': {},
#                 'interfaces': [],
#                 'resources': {},
#                 'services': {}
#             }
            
#             # Get system resource information
#             system_resource = api.get_resource('/system/resource')
#             system_info = system_resource.get()
#             if system_info:
#                 status_info['system'] = self._extract_system_info(system_info[0])
            
#             # Get interface information
#             interfaces = api.get_resource('/interface')
#             interface_list = interfaces.get()
#             for interface in interface_list[:10]:  # Limit to first 10 interfaces
#                 status_info['interfaces'].append({
#                     'name': interface.get('name'),
#                     'type': interface.get('type'),
#                     'running': interface.get('running') == 'true',
#                     'rx_bytes': interface.get('rx-byte'),
#                     'tx_bytes': interface.get('tx-byte')
#                 })
            
#             # Get resource usage
#             status_info['resources'] = {
#                 'cpu_load': system_info[0].get('cpu-load') if system_info else 'Unknown',
#                 'memory_usage': self._calculate_memory_usage(system_info[0]) if system_info else 'Unknown',
#                 'uptime': system_info[0].get('uptime') if system_info else 'Unknown'
#             }
            
#             # Get active services count
#             try:
#                 hotspot_active = api.get_resource('/ip/hotspot/active')
#                 status_info['services']['hotspot_users'] = len(hotspot_active.get())
#             except:
#                 status_info['services']['hotspot_users'] = 0
            
#             try:
#                 pppoe_active = api.get_resource('/ppp/active')
#                 status_info['services']['pppoe_users'] = len(pppoe_active.get())
#             except:
#                 status_info['services']['pppoe_users'] = 0
            
#             return status_info
            
#         except Exception as e:
#             logger.error(f"Failed to get router status for {self.ip}: {str(e)}")
#             return {
#                 'online': False,
#                 'error': str(e),
#                 'timestamp': self._get_current_timestamp()
#             }
#         finally:
#             if self.api_pool:
#                 try:
#                     self.api_pool.disconnect()
#                 except:
#                     pass
    
#     def _calculate_memory_usage(self, system_info: Dict) -> str:
#         """Calculate memory usage percentage."""
#         try:
#             free_memory = int(system_info.get('free-memory', 0))
#             total_memory = int(system_info.get('total-memory', 1))
#             usage_percent = ((total_memory - free_memory) / total_memory) * 100
#             return f"{usage_percent:.1f}%"
#         except (ValueError, ZeroDivisionError):
#             return "Unknown"
    
#     def disconnect(self):
#         """Clean up connections."""
#         if self.api_pool:
#             try:
#                 self.api_pool.disconnect()
#                 logger.debug(f"Disconnected from router {self.ip}")
#             except Exception as e:
#                 logger.warning(f"Error disconnecting from router {self.ip}: {str(e)}")
    
#     def __enter__(self):
#         """Context manager entry."""
#         return self
    
#     def __exit__(self, exc_type, exc_val, exc_tb):
#         """Context manager exit with proper cleanup."""
#         self.disconnect()


# class MikroTikConnectionManager:
#     """
#     Enhanced manager class for handling multiple MikroTik router connections with utility functions.
#     """
    
#     @staticmethod
#     def test_router_connection(ip: str, username: str, password: str, port: int = None, timeout: int = None) -> Dict:
#         """
#         Static method to test router connection without creating instance.
        
#         Returns:
#             dict: Connection test results
#         """
#         connection_config = MikroTikConfig.get_connection_config()
#         port = port or connection_config.get('PORT', 8728)
#         timeout = timeout or connection_config.get('TIMEOUT', 10)
        
#         connector = MikroTikConnector(ip, username, password, port, timeout)
#         return connector.test_connection()
    
#     @staticmethod
#     def validate_router_credentials(ip: str, username: str, password: str, port: int = None) -> Dict:
#         """
#         Validate router credentials and return capabilities.
        
#         Returns:
#             dict: Validation results and router capabilities
#         """
#         if not ROUTEROS_AVAILABLE:
#             return {
#                 'valid': False,
#                 'message': 'routeros-api package not installed',
#                 'capabilities': {}
#             }
        
#         connection_config = MikroTikConfig.get_connection_config()
#         port = port or connection_config.get('PORT', 8728)
        
#         connector = MikroTikConnector(ip, username, password, port)
#         test_results = connector.test_connection()
        
#         if not test_results.get('system_access'):
#             return {
#                 'valid': False,
#                 'message': 'Invalid credentials or router not accessible',
#                 'capabilities': {},
#                 'error_messages': test_results.get('error_messages', [])
#             }
        
#         return {
#             'valid': True,
#             'message': 'Credentials validated successfully',
#             'capabilities': test_results.get('capabilities', {}),
#             'system_info': test_results.get('system_info', {}),
#             'connection_info': {
#                 'response_time': test_results.get('response_time'),
#                 'basic_connectivity': test_results.get('basic_connectivity'),
#                 'api_connection': test_results.get('api_connection')
#             }
#         }
    
#     @staticmethod
#     def get_connection_templates() -> Dict:
#         """
#         Get predefined configuration templates for different use cases.
        
#         Returns:
#             dict: Configuration templates
#         """
#         hotspot_defaults = MikroTikConfig.get_hotspot_defaults()
#         pppoe_defaults = MikroTikConfig.get_pppoe_defaults()
        
#         return {
#             'public_wifi': {
#                 'name': 'Public WiFi Hotspot',
#                 'description': 'Standard configuration for public WiFi access',
#                 'hotspot_config': {
#                     'ssid': hotspot_defaults['default_ssid'],
#                     'bandwidth_limit': '5M/5M',
#                     'session_timeout': 120,
#                     'max_users': 100,
#                     'welcome_message': 'Welcome to our WiFi service',
#                     'ip_pool': '192.168.100.10-192.168.100.200'
#                 },
#                 'recommended_for': ['cafes', 'restaurants', 'public spaces']
#             },
#             'enterprise_hotspot': {
#                 'name': 'Enterprise Hotspot',
#                 'description': 'Advanced configuration for enterprise environments',
#                 'hotspot_config': {
#                     'ssid': f"{hotspot_defaults['default_ssid']}-Enterprise",
#                     'bandwidth_limit': '20M/20M',
#                     'session_timeout': 480,
#                     'max_users': 50,
#                     'welcome_message': 'Enterprise WiFi Access',
#                     'ip_pool': '192.168.200.10-192.168.200.100'
#                 },
#                 'pppoe_config': {
#                     'bandwidth_limit': '50M/50M',
#                     'mtu': 1500,
#                     'ip_pool_name': 'enterprise-pppoe-pool',
#                     'ip_range': '192.168.201.10-192.168.201.100'
#                 },
#                 'recommended_for': ['offices', 'business centers', 'corporate environments']
#             },
#             'isp_pppoe': {
#                 'name': 'ISP PPPoE Service',
#                 'description': 'Configuration for ISP-style PPPoE services',
#                 'pppoe_config': {
#                     'bandwidth_limit': '100M/50M',
#                     'mtu': 1492,
#                     'ip_pool_name': 'isp-pppoe-pool',
#                     'ip_range': '192.168.1.10-192.168.1.254',
#                     'service_name': 'ISP-PPPoE'
#                 },
#                 'recommended_for': ['internet service providers', 'wisp operations']
#             },
#             'basic_router': {
#                 'name': 'Basic Router Setup',
#                 'description': 'Minimal configuration for basic routing',
#                 'basic_config': {
#                     'enable_api': True,
#                     'enable_ssh': True,
#                     'enable_www': True
#                 },
#                 'recommended_for': ['basic routing', 'network gateways']
#             }
#         }
    
#     @staticmethod
#     def get_supported_models() -> Dict:
#         """
#         Get information about supported MikroTik models and their capabilities.
        
#         Returns:
#             dict: Supported models information
#         """
#         return {
#             'beginner_series': {
#                 'models': ['hAP lite', 'hAP ac', 'hAP ac²', 'hAP ax²'],
#                 'capabilities': ['hotspot', 'pppoe', 'basic_qos', 'wireless'],
#                 'max_users': 50,
#                 'description': 'Entry-level devices for small deployments'
#             },
#             'home_series': {
#                 'models': ['hEX', 'hEX S', 'hEX PoE'],
#                 'capabilities': ['hotspot', 'pppoe', 'advanced_qos', 'vlan'],
#                 'max_users': 100,
#                 'description': 'Home and small office routers'
#             },
#             'business_series': {
#                 'models': ['RB4011', 'RB5009', 'CCR1009'],
#                 'capabilities': ['hotspot', 'pppoe', 'advanced_qos', 'vlan', 'advanced_routing'],
#                 'max_users': 500,
#                 'description': 'Business-grade routers for larger deployments'
#             },
#             'service_provider': {
#                 'models': ['CCR2004', 'CCR2116', 'CCR2216'],
#                 'capabilities': ['hotspot', 'pppoe', 'advanced_qos', 'vlan', 'advanced_routing', 'high_performance'],
#                 'max_users': 1000,
#                 'description': 'Carrier-grade routers for service providers'
#             }
#         }
    
#     @staticmethod
#     def check_requirements() -> Dict:
#         """
#         Check system requirements and dependencies for MikroTik integration.
        
#         Returns:
#             dict: Requirements check results
#         """
#         return {
#             'routeros_api_available': ROUTEROS_AVAILABLE,
#             'django_available': DJANGO_AVAILABLE,
#             'python_version': {
#                 'current': '.'.join(map(str, sys.version_info[:3])),
#                 'required': '3.7+',
#                 'compatible': sys.version_info >= (3, 7)
#             },
#             'dependencies': {
#                 'routeros-api': ROUTEROS_AVAILABLE,
#                 'django': DJANGO_AVAILABLE,
#             },
#             'recommendations': [
#                 'Install routeros-api: pip install routeros-api',
#                 'For Django integration: ensure Django is properly configured',
#             ] if not ROUTEROS_AVAILABLE else []
#         }
    
#     @staticmethod
#     def cleanup_all_connections():
#         """Clean up all connection pools."""
#         ConnectionPoolManager.disconnect_all_pools()


# # Utility functions for common operations
# def quick_connection_test(ip: str, username: str, password: str, port: int = None) -> Tuple[bool, str]:
#     """
#     Quick connection test for basic validation.
    
#     Returns:
#         tuple: (success: bool, message: str)
#     """
#     try:
#         connection_config = MikroTikConfig.get_connection_config()
#         port = port or connection_config.get('PORT', 8728)
        
#         connector = MikroTikConnector(ip, username, password, port, timeout=5, max_retries=1)
#         test_results = connector.test_connection()
        
#         if test_results.get('system_access'):
#             return True, "Connection successful"
#         else:
#             errors = test_results.get('error_messages', ['Unknown error'])
#             return False, f"Connection failed: {errors[0]}"
            
#     except Exception as e:
#         return False, f"Connection test error: {str(e)}"


# def validate_mikrotik_configuration(config: Dict) -> Tuple[bool, List[str]]:
#     """
#     Validate MikroTik configuration parameters.
    
#     Returns:
#         tuple: (is_valid: bool, error_messages: list)
#     """
#     errors = []
    
#     required_fields = ['ip', 'username', 'password']
#     for field in required_fields:
#         if field not in config or not config[field]:
#             errors.append(f"Missing required field: {field}")
    
#     if 'ip' in config:
#         ip_pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
#         if not re.match(ip_pattern, config['ip']):
#             errors.append("Invalid IP address format")
    
#     if 'port' in config:
#         try:
#             port = int(config['port'])
#             if not (1 <= port <= 65535):
#                 errors.append("Port must be between 1 and 65535")
#         except (ValueError, TypeError):
#             errors.append("Port must be a valid number")
    
#     return len(errors) == 0, errors


# def get_connector_version() -> Dict[str, str]:
#     """
#     Get the version information for the MikroTik connector.
    
#     Returns:
#         dict: Version information
#     """
#     return {
#         'version': '2.1.0',
#         'compatibility': 'MikroTik RouterOS 6.0+',
#         'dependencies': {
#             'routeros_api': '2.3.0+',
#             'python': '3.7+',
#             'django': '3.2+'
#         },
#         'features': [
#             'Enhanced security with SSL/TLS support',
#             'Connection pooling with monitoring',
#             'Database integration with MySQL',
#             'Environment-aware configuration',
#             'Hotspot and PPPoE configuration',
#             'Comprehensive error handling'
#         ]
#     }


# # Export main classes and functions
# __all__ = [
#     'MikroTikConnector',
#     'MikroTikConnectionManager',
#     'ConnectionPoolManager',
#     'SecurityConfig',
#     'MikroTikConfig',
#     'MonitoringManager',
#     'DatabaseManager',
#     'quick_connection_test',
#     'validate_mikrotik_configuration',
#     'get_connector_version'
# ]







"""
PRODUCTION-READY MikroTik Router Connector Utility - ENHANCED

Enhanced with better settings integration, security, and database compatibility.
"""

import os
import logging
import socket
import time
import re
import sys
import ssl
import datetime
import ipaddress
from typing import Dict, Tuple, Optional, Any, List

# Django imports with better fallbacks
try:
    from django.conf import settings
    from django.core.cache import cache
    from django.db import transaction
    from django.utils import timezone
    from django.db import models
    DJANGO_AVAILABLE = True
except ImportError:
    DJANGO_AVAILABLE = False
    # Enhanced fallback implementations
    timezone = datetime.datetime
    class SimpleCache:
        def get(self, key, default=None): return default
        def set(self, key, value, timeout=None): pass
        def delete(self, key): pass
    cache = SimpleCache()
    settings = type('Settings', (), {})()
    transaction = type('Transaction', (), {'atomic': lambda: type('Context', (), {'__enter__': lambda self: None, '__exit__': lambda self, *args: None})()})()
    models = type('Models', (), {'Avg': lambda x: x})()

# RouterOS API imports
try:
    from routeros_api import RouterOsApiPool
    from routeros_api.exceptions import RouterOsApiConnectionError, RouterOsApiCommunicationError
    ROUTEROS_AVAILABLE = True
except ImportError:
    ROUTEROS_AVAILABLE = False
    class RouterOsApiPool:
        def __init__(self, *args, **kwargs):
            raise ImportError("routeros-api package not installed")
        def get_api(self): pass
        def disconnect(self): pass
        @property
        def active_count(self): return 0
    RouterOsApiConnectionError = RouterOsApiCommunicationError = Exception

logger = logging.getLogger(__name__)


class SecurityConfig:
    """Security configuration management with proper certificate handling."""
    
    @staticmethod
    def get_ssl_context():
        """Create SSL context with proper certificate verification."""
        context = ssl.create_default_context()
        
        try:
            # Get SSL configuration from Django settings
            ssl_verify = getattr(settings, 'MIKROTIK_CONFIG', {}).get('CONNECTION', {}).get('SSL_VERIFY', True)
        except:
            ssl_verify = True
        
        if ssl_verify:
            # Production: Verify certificates
            try:
                ca_cert_path = getattr(settings, 'MIKROTIK_CONFIG', {}).get('CONNECTION', {}).get('SSL_CA_CERT_PATH')
            except:
                ca_cert_path = None
                
            if ca_cert_path and os.path.exists(ca_cert_path):
                context.load_verify_locations(ca_cert_path)
            context.verify_mode = ssl.CERT_REQUIRED
        else:
            # Development: Allow self-signed certificates with warning
            logger.warning("SSL verification disabled - not recommended for production")
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
        return context
    
    @staticmethod
    def validate_credentials(ip: str, username: str, password: str) -> Tuple[bool, List[str]]:
        """Validate credentials before connection attempts."""
        errors = []
        
        try:
            # Security validation from settings
            security_config = getattr(settings, 'MIKROTIK_CONFIG', {}).get('SECURITY', {})
            validate_credentials = security_config.get('VALIDATE_CREDENTIALS', True)
            reject_default_passwords = security_config.get('REJECT_DEFAULT_PASSWORDS', True)
        except:
            validate_credentials = True
            reject_default_passwords = True
        
        if not validate_credentials:
            return True, errors
            
        # Check for default credentials
        if reject_default_passwords and username == 'admin' and password in ['', 'admin']:
            errors.append("Default credentials detected - change for security")
            
        # Check password strength
        if len(password) < 8:
            errors.append("Password too short - minimum 8 characters required")
            
        # Check IP format
        if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
            errors.append("Invalid IP address format")
            
        return len(errors) == 0, errors


class MikroTikConfig:
    """Externalized configuration management using Django settings."""
    
    @classmethod
    def get_connection_config(cls) -> Dict:
        """Get connection configuration from settings."""
        try:
            return getattr(settings, 'MIKROTIK_CONFIG', {}).get('CONNECTION', {})
        except:
            return {
                'TIMEOUT': 10,
                'MAX_RETRIES': 3,
                'PORT': 8728,
                'USE_SSL': False,
                'SSL_VERIFY': True
            }
    
    @classmethod
    def get_pool_config(cls) -> Dict:
        """Get pool configuration from settings."""
        try:
            return getattr(settings, 'MIKROTIK_CONFIG', {}).get('POOL', {})
        except:
            return {
                'MAX_CONNECTIONS': 5,
                'CLEANUP_INTERVAL': 300,
                'CACHE_TIMEOUT': 300
            }
    
    @classmethod
    def get_monitoring_config(cls) -> Dict:
        """Get monitoring configuration from settings."""
        try:
            return getattr(settings, 'MIKROTIK_CONFIG', {}).get('MONITORING', {})
        except:
            return {
                'ENABLED': True,
                'MAX_RESPONSE_TIME_ALERT': 5.0
            }
    
    @classmethod
    def get_logging_config(cls) -> Dict:
        """Get logging configuration from settings."""
        try:
            return getattr(settings, 'MIKROTIK_CONFIG', {}).get('LOGGING', {})
        except:
            return {
                'SAVE_CONNECTION_TESTS': True
            }
    
    @classmethod
    def get_hotspot_defaults(cls):
        """Get hotspot configuration defaults from settings."""
        try:
            hotspot_config = getattr(settings, 'MIKROTIK_CONFIG', {}).get('HOTSPOT', {})
            return {
                'ip_pool': hotspot_config.get('IP_POOL', '192.168.100.10-192.168.100.200'),
                'bandwidth_limit': hotspot_config.get('BANDWIDTH_LIMIT', '10M/10M'),
                'session_timeout': hotspot_config.get('SESSION_TIMEOUT', 60),
                'max_users': hotspot_config.get('MAX_USERS', 50),
                'default_ssid': hotspot_config.get('DEFAULT_SSID', 'SurfZone-WiFi'),
            }
        except:
            return {
                'ip_pool': '192.168.100.10-192.168.100.200',
                'bandwidth_limit': '10M/10M',
                'session_timeout': 60,
                'max_users': 50,
                'default_ssid': 'SurfZone-WiFi',
            }
    
    @classmethod
    def get_pppoe_defaults(cls):
        """Get PPPoE configuration defaults from settings."""
        try:
            pppoe_config = getattr(settings, 'MIKROTIK_CONFIG', {}).get('PPPOE', {})
            return {
                'ip_pool_name': pppoe_config.get('IP_POOL_NAME', 'pppoe-pool'),
                'ip_range': pppoe_config.get('IP_RANGE', '192.168.101.10-192.168.101.200'),
                'bandwidth_limit': pppoe_config.get('BANDWIDTH_LIMIT', '10M/10M'),
                'mtu': pppoe_config.get('MTU', 1492),
                'service_name': pppoe_config.get('SERVICE_NAME', 'PPPoE-Service'),
            }
        except:
            return {
                'ip_pool_name': 'pppoe-pool',
                'ip_range': '192.168.101.10-192.168.101.200',
                'bandwidth_limit': '10M/10M',
                'mtu': 1492,
                'service_name': 'PPPoE-Service',
            }


class MonitoringManager:
    """Monitoring and alerting management."""
    
    @staticmethod
    def record_connection_attempt(router_ip: str, success: bool):
        """Record connection attempt metrics."""
        monitoring_config = MikroTikConfig.get_monitoring_config()
        if not monitoring_config.get('ENABLED', True):
            return
            
        status = 'success' if success else 'failure'
        logger.info(f"Connection attempt to {router_ip}: {status}")
    
    @staticmethod
    def record_configuration_attempt(router_ip: str, config_type: str, success: bool):
        """Record configuration attempt metrics."""
        monitoring_config = MikroTikConfig.get_monitoring_config()
        if not monitoring_config.get('ENABLED', True):
            return
            
        status = 'success' if success else 'failure'
        logger.info(f"Configuration attempt {config_type} on {router_ip}: {status}")
    
    @staticmethod
    def record_response_time(router_ip: str, operation: str, duration: float):
        """Record response time metrics."""
        monitoring_config = MikroTikConfig.get_monitoring_config()
        if not monitoring_config.get('ENABLED', True):
            return
            
        max_response_time = monitoring_config.get('MAX_RESPONSE_TIME_ALERT', 5.0)
        if duration > max_response_time:
            logger.warning(f"High response time for {operation} on {router_ip}: {duration:.2f}s")
    
    @staticmethod
    def check_performance_thresholds(router, response_time: float, success: bool):
        """Check performance thresholds and create alerts."""
        if not DJANGO_AVAILABLE:
            return
            
        monitoring_config = MikroTikConfig.get_monitoring_config()
        max_response_time = monitoring_config.get('MAX_RESPONSE_TIME_ALERT', 5.0)
        
        if response_time > max_response_time:
            MonitoringManager._create_performance_alert(
                router, 
                f"High response time: {response_time:.2f}s (threshold: {max_response_time}s)"
            )
        
        if not success:
            MonitoringManager._create_connection_alert(router, "Connection failed")
    
    @staticmethod
    def _create_performance_alert(router, message: str):
        """Create performance alert in database."""
        try:
            # Import models here to avoid circular imports
            from network_management.models.router_management_model import RouterHealthCheck
            RouterHealthCheck.objects.create(
                router=router,
                is_online=True,
                response_time=None,
                error_message=message,
                health_score=60,
                critical_alerts=[message],
                performance_metrics={'high_response_time': True}
            )
            logger.warning(f"Performance alert for {router.ip}: {message}")
        except Exception as e:
            logger.error(f"Failed to create performance alert: {str(e)}")
    
    @staticmethod
    def _create_connection_alert(router, message: str):
        """Create connection alert in database."""
        try:
            # Import models here to avoid circular imports
            from network_management.models.router_management_model import RouterHealthCheck
            RouterHealthCheck.objects.create(
                router=router,
                is_online=False,
                response_time=None,
                error_message=message,
                health_score=0,
                critical_alerts=[message],
                performance_metrics={}
            )
            logger.warning(f"Connection alert for {router.ip}: {message}")
        except Exception as e:
            logger.error(f"Failed to create connection alert: {str(e)}")


class ConnectionPoolManager:
    """
    Enhanced connection pooling manager with security and monitoring.
    """
    
    _pools = {}
    
    @classmethod
    def get_pool(cls, ip: str, username: str, password: str, port: int = None, 
                 router_id: int = None) -> Any:
        """Get or create a secure connection pool for a router."""
        if not ROUTEROS_AVAILABLE:
            raise ImportError("routeros-api package is required for MikroTik connections")
        
        # Security validation
        is_valid, errors = SecurityConfig.validate_credentials(ip, username, password)
        if not is_valid:
            logger.warning(f"Security validation failed for {ip}: {', '.join(errors)}")
        
        connection_config = MikroTikConfig.get_connection_config()
        pool_config = MikroTikConfig.get_pool_config()
        
        port = port or connection_config.get('PORT', 8728)
        pool_key = f"{ip}:{port}:{username}"
        
        # Clean up old pools periodically
        cls._cleanup_old_pools()
        
        if pool_key not in cls._pools:
            try:
                use_ssl = connection_config.get('USE_SSL', False)
                ssl_verify = connection_config.get('SSL_VERIFY', True)
                
                pool = RouterOsApiPool(
                    host=ip,
                    username=username,
                    password=password,
                    port=port,
                    plaintext_login=True,
                    use_ssl=use_ssl,
                    ssl_verify=ssl_verify,
                    timeout=connection_config.get('TIMEOUT', 10),
                    max_connections=pool_config.get('MAX_CONNECTIONS', 5)
                )
                
                cls._pools[pool_key] = {
                    'pool': pool,
                    'last_used': time.time(),
                    'use_count': 0,
                    'created_at': time.time(),
                    'router_id': router_id
                }
                
                logger.info(f"Created new secure connection pool for {ip}:{port}")
                
            except Exception as e:
                logger.error(f"Failed to create connection pool for {ip}:{port}: {str(e)}")
                MonitoringManager.record_connection_attempt(ip, False)
                raise
        
        cls._pools[pool_key]['last_used'] = time.time()
        cls._pools[pool_key]['use_count'] += 1
        
        return cls._pools[pool_key]['pool']
    
    @classmethod
    def _cleanup_old_pools(cls):
        """Clean up pools that haven't been used recently."""
        current_time = time.time()
        pool_config = MikroTikConfig.get_pool_config()
        cleanup_interval = pool_config.get('CLEANUP_INTERVAL', 300)
        pools_to_remove = []
        
        for pool_key, pool_info in cls._pools.items():
            if current_time - pool_info['last_used'] > cleanup_interval:
                try:
                    pool_info['pool'].disconnect()
                    pools_to_remove.append(pool_key)
                    logger.info(f"Cleaned up unused connection pool: {pool_key}")
                except Exception as e:
                    logger.warning(f"Error cleaning up pool {pool_key}: {str(e)}")
        
        for pool_key in pools_to_remove:
            del cls._pools[pool_key]
    
    @classmethod
    def get_pool_stats(cls) -> Dict:
        """Get statistics about connection pools."""
        return {
            'total_pools': len(cls._pools),
            'pools': {
                key: {
                    'use_count': info['use_count'],
                    'last_used': info['last_used'],
                    'created_at': info['created_at'],
                    'router_id': info.get('router_id')
                } for key, info in cls._pools.items()
            }
        }
    
    @classmethod
    def disconnect_pool(cls, ip: str, port: int = None, username: str = None):
        """Disconnect specific pool."""
        connection_config = MikroTikConfig.get_connection_config()
        port = port or connection_config.get('PORT', 8728)
        
        if username:
            pool_key = f"{ip}:{port}:{username}"
        else:
            # Find by IP and port only
            pool_key = next((k for k in cls._pools.keys() if k.startswith(f"{ip}:{port}:")), None)
        
        if pool_key and pool_key in cls._pools:
            try:
                cls._pools[pool_key]['pool'].disconnect()
                del cls._pools[pool_key]
                logger.info(f"Disconnected pool: {pool_key}")
            except Exception as e:
                logger.error(f"Error disconnecting pool {pool_key}: {str(e)}")
    
    @classmethod
    def disconnect_all_pools(cls):
        """Disconnect all connection pools."""
        pools_to_remove = list(cls._pools.keys())
        for pool_key in pools_to_remove:
            try:
                cls._pools[pool_key]['pool'].disconnect()
                del cls._pools[pool_key]
                logger.info(f"Disconnected pool: {pool_key}")
            except Exception as e:
                logger.error(f"Error disconnecting pool {pool_key}: {str(e)}")
        
        logger.info("All connection pools disconnected")


class DatabaseManager:
    """MySQL database operations manager."""
    
    @staticmethod
    def save_connection_test(router, test_results: Dict, user=None):
        """Save connection test results to database."""
        if not DJANGO_AVAILABLE:
            return None
            
        logging_config = MikroTikConfig.get_logging_config()
        if not logging_config.get('SAVE_CONNECTION_TESTS', True):
            return None
            
        try:
            # Import models here to avoid circular imports
            from network_management.models.router_management_model import RouterConnectionTest
            
            with transaction.atomic():
                connection_test = RouterConnectionTest.objects.create(
                    router=router,
                    success=test_results.get('system_access', False),
                    response_time=test_results.get('response_time'),
                    system_info=test_results.get('system_info', {}),
                    error_messages=test_results.get('error_messages', []),
                    tested_by=user
                )
                
                # Update router status
                router.connection_status = 'connected' if test_results.get('system_access') else 'disconnected'
                router.last_connection_test = timezone.now()
                
                if test_results.get('system_info'):
                    router.firmware_version = test_results['system_info'].get('version', router.firmware_version)
                
                router.save()
                
                return connection_test
                
        except Exception as e:
            logger.error(f"Failed to save connection test for router {router.id}: {str(e)}")
            return None
    
    @staticmethod
    def create_audit_log(router, action: str, description: str, 
                        user=None, ip_address: str = None, changes: Dict = None):
        """Create audit log entry."""
        if not DJANGO_AVAILABLE:
            return
            
        try:
            # Import models here to avoid circular imports
            from network_management.models.router_management_model import RouterAuditLog
            RouterAuditLog.objects.create(
                router=router,
                action=action,
                description=description,
                user=user,
                ip_address=ip_address,
                changes=changes or {}
            )
        except Exception as e:
            logger.error(f"Failed to create audit log: {str(e)}")
    
    @staticmethod
    def update_router_configuration_status(router, config_type: str, success: bool, 
                                         errors: List[str] = None):
        """Update router configuration status."""
        if not DJANGO_AVAILABLE:
            return
            
        try:
            if success:
                if router.configuration_status == 'not_configured':
                    router.configuration_status = 'configured'
                elif router.configuration_status == 'partially_configured':
                    router.configuration_status = 'configured'
                router.configuration_type = config_type
            else:
                if router.configuration_status == 'configured':
                    router.configuration_status = 'partially_configured'
                else:
                    router.configuration_status = 'configuration_failed'
            
            router.last_configuration_update = timezone.now()
            router.save()
            
        except Exception as e:
            logger.error(f"Failed to update router configuration status: {str(e)}")


class MikroTikConnector:
    """
    PRODUCTION-READY MikroTik router connection and configuration manager.
    Enhanced with security, monitoring, and database integration.
    """
    
    def __init__(self, ip: str, username: str, password: str, port: int = None, 
                 timeout: int = None, max_retries: int = None, use_ssl: bool = None,
                 router_id: int = None):
        self.ip = ip
        self.username = username
        self.password = password
        
        # Get configuration from settings
        connection_config = MikroTikConfig.get_connection_config()
        self.port = port or connection_config.get('PORT', 8728)
        self.timeout = timeout or connection_config.get('TIMEOUT', 10)
        self.max_retries = max_retries or connection_config.get('MAX_RETRIES', 3)
        self.use_ssl = use_ssl if use_ssl is not None else connection_config.get('USE_SSL', False)
        self.router_id = router_id
        
        self.api_pool = None
        self.api = None
        
        # Validate parameters
        self._validate_parameters()
    
    def _validate_parameters(self):
        """Validate connection parameters with security checks."""
        if not self.ip or not self.username:
            raise ValueError("IP address and username are required")
        
        if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', self.ip):
            raise ValueError("Invalid IP address format")
        
        if not (1 <= self.port <= 65535):
            raise ValueError("Port must be between 1 and 65535")
        
        # Security validation
        is_valid, errors = SecurityConfig.validate_credentials(self.ip, self.username, self.password)
        if not is_valid:
            logger.warning(f"Security issues detected: {', '.join(errors)}")
    
    def connect(self, user=None) -> Tuple[bool, str, Any]:
        """
        Enhanced secure connection establishment with monitoring and database logging.
        """
        pool_config = MikroTikConfig.get_pool_config()
        cache_key = f"router_connection:{self.ip}:{self.port}"
        cached_result = cache.get(cache_key)
        
        # Check cached connection
        if cached_result and cached_result.get('status') == 'connected':
            cache_age = time.time() - cached_result.get('timestamp', 0)
            cache_timeout = pool_config.get('CACHE_TIMEOUT', 300)
            if cache_age < cache_timeout:
                logger.debug(f"Using cached connection for {self.ip}")
                return True, "Connection verified from cache", cached_result.get('api_data')
        
        start_time = time.time()
        
        # Attempt connection with retries
        for attempt in range(self.max_retries):
            try:
                # Test basic connectivity first
                if not self._test_connectivity():
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Connectivity test failed for {self.ip}, attempt {attempt + 1}. Retrying in {wait_time}s")
                    time.sleep(wait_time)
                    continue
                
                # Use secure connection pool
                self.api_pool = ConnectionPoolManager.get_pool(
                    self.ip, self.username, self.password, self.port, self.router_id
                )
                
                self.api = self.api_pool.get_api()
                
                # Verify connection by fetching system info
                system_resource = self.api.get_resource('/system/resource')
                system_info = system_resource.get()
                
                if not system_info:
                    logger.warning(f"No system info received from {self.ip}, attempt {attempt + 1}")
                    continue
                
                # Cache successful connection
                connection_data = {
                    'status': 'connected',
                    'system_info': system_info[0],
                    'timestamp': time.time(),
                    'api_data': self.api
                }
                cache.set(cache_key, connection_data, pool_config.get('CACHE_TIMEOUT', 300))
                
                response_time = time.time() - start_time
                
                # Record metrics
                MonitoringManager.record_connection_attempt(self.ip, True)
                MonitoringManager.record_response_time(self.ip, 'connect', response_time)
                
                logger.info(f"Successfully connected to MikroTik router at {self.ip} (attempt {attempt + 1}, response time: {response_time:.2f}s)")
                return True, "Connection established successfully", self.api
                
            except RouterOsApiConnectionError as e:
                error_msg = f"Connection failed (attempt {attempt + 1}): {str(e)}"
                logger.warning(f"MikroTik connection error for {self.ip}: {error_msg}")
                MonitoringManager.record_connection_attempt(self.ip, False)
                
                if attempt == self.max_retries - 1:
                    return False, error_msg, None
                time.sleep(2 ** attempt)
                
            except RouterOsApiCommunicationError as e:
                error_msg = f"Authentication failed (attempt {attempt + 1}): {str(e)}"
                logger.error(f"MikroTik authentication error for {self.ip}: {error_msg}")
                MonitoringManager.record_connection_attempt(self.ip, False)
                return False, error_msg, None
                
            except Exception as e:
                error_msg = f"Unexpected error (attempt {attempt + 1}): {str(e)}"
                logger.error(f"MikroTik unexpected error for {self.ip}: {error_msg}")
                MonitoringManager.record_connection_attempt(self.ip, False)
                
                if attempt == self.max_retries - 1:
                    return False, error_msg, None
                time.sleep(2 ** attempt)
        
        return False, "All connection attempts failed", None
    
    def _test_connectivity(self) -> bool:
        """Enhanced network connectivity test with timeout."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((self.ip, self.port))
            sock.close()
            
            if result == 0:
                logger.debug(f"Connectivity test passed for {self.ip}:{self.port}")
                return True
            else:
                logger.warning(f"Connectivity test failed for {self.ip}:{self.port} (error code: {result})")
                return False
                
        except Exception as e:
            logger.error(f"Connectivity test exception for {self.ip}:{self.port}: {str(e)}")
            return False
    
    def test_connection(self, user=None) -> Dict[str, Any]:
        """
        Comprehensive connection test with monitoring and database storage.
        """
        if not ROUTEROS_AVAILABLE:
            test_results = {
                'ip': self.ip,
                'port': self.port,
                'timestamp': self._get_current_timestamp(),
                'basic_connectivity': False,
                'api_connection': False,
                'authentication': False,
                'system_access': False,
                'response_time': None,
                'system_info': {},
                'error_messages': ['routeros-api package not installed'],
                'attempts_made': 0,
                'capabilities': {}
            }
            
            # Still save to database even if connector not available
            if self.router_id and DJANGO_AVAILABLE:
                try:
                    # Import models here to avoid circular imports
                    from network_management.models.router_management_model import Router
                    router = Router.objects.get(id=self.router_id)
                    DatabaseManager.save_connection_test(router, test_results, user)
                except Exception as e:
                    logger.warning(f"Failed to save connection test for router {self.router_id}: {str(e)}")
                    
            return test_results
        
        start_time = time.time()
        
        test_results = {
            'ip': self.ip,
            'port': self.port,
            'timestamp': self._get_current_timestamp(),
            'basic_connectivity': False,
            'api_connection': False,
            'authentication': False,
            'system_access': False,
            'response_time': None,
            'system_info': {},
            'capabilities': {},
            'error_messages': [],
            'attempts_made': 0,
            'recommendations': []
        }
        
        for attempt in range(self.max_retries):
            test_results['attempts_made'] = attempt + 1
            
            try:
                # Test 1: Basic network connectivity
                test_results['basic_connectivity'] = self._test_connectivity()
                if not test_results['basic_connectivity']:
                    error_msg = f"Attempt {attempt + 1}: Network connectivity test failed"
                    test_results['error_messages'].append(error_msg)
                    test_results['recommendations'].append("Check network connectivity and firewall rules")
                    if attempt < self.max_retries - 1:
                        time.sleep(1)
                        continue
                    break
                
                # Test 2: API Connection and Authentication
                success, message, api = self.connect(user)
                
                if not success:
                    test_results['error_messages'].append(f"Attempt {attempt + 1}: {message}")
                    if attempt < self.max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    break
                
                test_results['api_connection'] = True
                test_results['authentication'] = True
                
                # Test 3: System access and information retrieval
                try:
                    system_resource = api.get_resource('/system/resource')
                    system_info = system_resource.get()
                    
                    if system_info:
                        test_results['system_access'] = True
                        test_results['system_info'] = self._extract_system_info(system_info[0])
                        test_results['capabilities'] = self._determine_capabilities(system_info[0])
                        
                        # Get additional router information
                        self._get_additional_router_info(api, test_results)
                    
                    # Calculate response time
                    end_time = time.time()
                    test_results['response_time'] = end_time - start_time
                    
                    # Generate recommendations
                    self._generate_recommendations(test_results)
                    
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    error_msg = f"Attempt {attempt + 1}: System access failed: {str(e)}"
                    test_results['error_messages'].append(error_msg)
                    if attempt < self.max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                
            except Exception as e:
                error_msg = f"Attempt {attempt + 1}: Unexpected error: {str(e)}"
                test_results['error_messages'].append(error_msg)
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
        
        # Cleanup
        if self.api_pool:
            try:
                self.api_pool.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting pool during test: {str(e)}")
        
        # Save to database
        if self.router_id and DJANGO_AVAILABLE:
            try:
                # Import models here to avoid circular imports
                from network_management.models.router_management_model import Router
                router = Router.objects.get(id=self.router_id)
                DatabaseManager.save_connection_test(router, test_results, user)
                
                # Performance monitoring
                MonitoringManager.check_performance_thresholds(
                    router, 
                    test_results.get('response_time', 0),
                    test_results.get('system_access', False)
                )
                
            except Exception as e:
                logger.warning(f"Router with ID {self.router_id} not found for connection test: {str(e)}")
        
        return test_results

    def _get_current_timestamp(self):
        """Get current timestamp in ISO format."""
        if DJANGO_AVAILABLE:
            return timezone.now().isoformat()
        else:
            return datetime.datetime.now().isoformat()
    
    def configure_hotspot(self, ssid: str = None, welcome_message: str = None, bandwidth_limit: str = None, 
                         session_timeout: int = None, max_users: int = None, redirect_url: str = None,
                         ip_pool: str = None, user=None) -> Tuple[bool, str, Dict]:
        """
        Enhanced hotspot configuration with security, monitoring, and database integration.
        """
        start_time = time.time()
        
        # Use configured defaults
        defaults = MikroTikConfig.get_hotspot_defaults()
        ssid = ssid or defaults['default_ssid']
        bandwidth_limit = bandwidth_limit or defaults['bandwidth_limit']
        session_timeout = session_timeout or defaults['session_timeout']
        max_users = max_users or defaults['max_users']
        ip_pool = ip_pool or defaults['ip_pool']
        
        try:
            success, message, api = self.connect(user)
            if not success:
                MonitoringManager.record_configuration_attempt(self.ip, 'hotspot', False)
                return False, message, {}
            
            configuration_steps = []
            config_details = {
                'ssid': ssid,
                'bandwidth_limit': bandwidth_limit,
                'session_timeout': session_timeout,
                'max_users': max_users,
                'steps_completed': [],
                'failed_steps': []
            }
            
            # Validate parameters
            validation_errors = self._validate_hotspot_parameters(ssid, bandwidth_limit, session_timeout, max_users)
            if validation_errors:
                MonitoringManager.record_configuration_attempt(self.ip, 'hotspot', False)
                return False, f"Parameter validation failed: {', '.join(validation_errors)}", config_details
            
            try:
                # Step 1: Configure IP pool
                pool_step = self._configure_ip_pool(api, 'hotspot-pool', ip_pool)
                configuration_steps.append(pool_step)
                
                # Step 2: Configure wireless interface
                wireless_step = self._configure_wireless_interface(api, ssid)
                configuration_steps.append(wireless_step)
                
                # Step 3: Configure hotspot server
                hotspot_step = self._configure_hotspot_server(api, ssid, redirect_url)
                configuration_steps.append(hotspot_step)
                
                # Step 4: Configure hotspot profile
                profile_step = self._configure_hotspot_profile(
                    api, bandwidth_limit, session_timeout, welcome_message
                )
                configuration_steps.append(profile_step)
                
                # Step 5: Configure user profiles
                user_step = self._configure_user_profiles(api, max_users, bandwidth_limit)
                configuration_steps.append(user_step)
                
                # Step 6: Configure firewall rules
                firewall_step = self._configure_hotspot_firewall(api)
                configuration_steps.append(firewall_step)
                
            except Exception as e:
                logger.error(f"Hotspot configuration steps failed: {str(e)}")
                MonitoringManager.record_configuration_attempt(self.ip, 'hotspot', False)
                return False, f"Configuration steps failed: {str(e)}", config_details
            
            finally:
                # Always attempt to cleanup connection
                try:
                    if self.api_pool:
                        self.api_pool.disconnect()
                except Exception as e:
                    logger.warning(f"Error during connection cleanup: {str(e)}")
            
            # Compile results
            for step in configuration_steps:
                if step['success']:
                    config_details['steps_completed'].append(step['step'])
                else:
                    config_details['failed_steps'].append({
                        'step': step['step'],
                        'error': step.get('error', 'Unknown error')
                    })
            
            config_details['configuration_steps'] = configuration_steps
            
            failed_count = len(config_details['failed_steps'])
            overall_success = failed_count == 0
            
            # Record metrics
            response_time = time.time() - start_time
            MonitoringManager.record_configuration_attempt(self.ip, 'hotspot', overall_success)
            MonitoringManager.record_response_time(self.ip, 'configure_hotspot', response_time)
            
            # Update database
            if self.router_id and DJANGO_AVAILABLE:
                try:
                    # Import models here to avoid circular imports
                    from network_management.models.router_management_model import Router
                    router = Router.objects.get(id=self.router_id)
                    DatabaseManager.update_router_configuration_status(
                        router, 'hotspot', overall_success, 
                        [step['error'] for step in config_details['failed_steps']]
                    )
                    
                    # Create audit log
                    DatabaseManager.create_audit_log(
                        router=router,
                        action='configure',
                        description=f"Hotspot configuration {'completed successfully' if overall_success else 'partially failed'}",
                        user=user,
                        changes=config_details
                    )
                    
                except Exception as e:
                    logger.warning(f"Router with ID {self.router_id} not found for configuration update: {str(e)}")
            
            if overall_success:
                return True, "Hotspot configuration completed successfully", config_details
            elif failed_count < len(configuration_steps):
                return False, f"Hotspot configuration partially completed ({failed_count} failures)", config_details
            else:
                return False, "Hotspot configuration failed completely", config_details
                
        except Exception as e:
            logger.error(f"Hotspot configuration failed for {self.ip}: {str(e)}")
            MonitoringManager.record_configuration_attempt(self.ip, 'hotspot', False)
            return False, f"Configuration failed: {str(e)}", {}
    
    def configure_pppoe(self, service_name: str = None, bandwidth_limit: str = None, 
                       mtu: int = None, ip_pool_name: str = None, 
                       ip_range: str = None, user=None) -> Tuple[bool, str, Dict]:
        """
        Enhanced PPPoE configuration with security, monitoring, and database integration.
        """
        start_time = time.time()
        
        # Use configured defaults
        defaults = MikroTikConfig.get_pppoe_defaults()
        service_name = service_name or defaults.get('service_name', 'PPPoE-Service')
        bandwidth_limit = bandwidth_limit or defaults['bandwidth_limit']
        mtu = mtu or defaults['mtu']
        ip_pool_name = ip_pool_name or defaults['ip_pool_name']
        ip_range = ip_range or defaults['ip_range']
        
        try:
            success, message, api = self.connect(user)
            if not success:
                MonitoringManager.record_configuration_attempt(self.ip, 'pppoe', False)
                return False, message, {}
            
            configuration_steps = []
            config_details = {
                'service_name': service_name,
                'bandwidth_limit': bandwidth_limit,
                'mtu': mtu,
                'ip_pool_name': ip_pool_name,
                'steps_completed': [],
                'failed_steps': []
            }
            
            try:
                # Step 1: Configure IP pool for PPPoE
                pool_step = self._configure_ip_pool(api, ip_pool_name, ip_range)
                configuration_steps.append(pool_step)
                
                # Step 2: Configure PPPoE server
                pppoe_step = self._configure_pppoe_server(api, service_name, mtu)
                configuration_steps.append(pppoe_step)
                
                # Step 3: Configure PPP profiles
                profile_step = self._configure_ppp_profiles(api, bandwidth_limit, ip_pool_name)
                configuration_steps.append(profile_step)
                
                # Step 4: Configure PPPoE secrets (example user)
                secret_step = self._configure_pppoe_secrets(api)
                configuration_steps.append(secret_step)
                
            except Exception as e:
                logger.error(f"PPPoE configuration steps failed: {str(e)}")
                MonitoringManager.record_configuration_attempt(self.ip, 'pppoe', False)
                return False, f"Configuration steps failed: {str(e)}", config_details
            
            finally:
                try:
                    if self.api_pool:
                        self.api_pool.disconnect()
                except Exception as e:
                    logger.warning(f"Error during connection cleanup: {str(e)}")
            
            # Compile results
            for step in configuration_steps:
                if step['success']:
                    config_details['steps_completed'].append(step['step'])
                else:
                    config_details['failed_steps'].append({
                        'step': step['step'],
                        'error': step.get('error', 'Unknown error')
                    })
            
            config_details['configuration_steps'] = configuration_steps
            
            failed_count = len(config_details['failed_steps'])
            overall_success = failed_count == 0
            
            # Record metrics
            response_time = time.time() - start_time
            MonitoringManager.record_configuration_attempt(self.ip, 'pppoe', overall_success)
            MonitoringManager.record_response_time(self.ip, 'configure_pppoe', response_time)
            
            # Update database
            if self.router_id and DJANGO_AVAILABLE:
                try:
                    # Import models here to avoid circular imports
                    from network_management.models.router_management_model import Router
                    router = Router.objects.get(id=self.router_id)
                    DatabaseManager.update_router_configuration_status(
                        router, 'pppoe', overall_success,
                        [step['error'] for step in config_details['failed_steps']]
                    )
                    
                    # Create audit log
                    DatabaseManager.create_audit_log(
                        router=router,
                        action='configure',
                        description=f"PPPoE configuration {'completed successfully' if overall_success else 'partially failed'}",
                        user=user,
                        changes=config_details
                    )
                    
                except Exception as e:
                    logger.warning(f"Router with ID {self.router_id} not found for configuration update: {str(e)}")
            
            if overall_success:
                return True, "PPPoE configuration completed successfully", config_details
            elif failed_count < len(configuration_steps):
                return False, f"PPPoE configuration partially completed ({failed_count} failures)", config_details
            else:
                return False, "PPPoE configuration failed completely", config_details
                
        except Exception as e:
            logger.error(f"PPPoE configuration failed for {self.ip}: {str(e)}")
            MonitoringManager.record_configuration_attempt(self.ip, 'pppoe', False)
            return False, f"Configuration failed: {str(e)}", {}
    
    # Configuration helper methods
    def _configure_ip_pool(self, api, pool_name: str, ip_range: str) -> Dict:
        """Configure IP pool."""
        try:
            ip_pool = api.get_resource('/ip/pool')
            existing_pools = ip_pool.get(name=pool_name)
            
            if existing_pools:
                ip_pool.set(id=existing_pools[0].get('.id'), ranges=ip_range)
                return {'step': 'ip_pool', 'success': True, 'action': 'updated', 'pool_name': pool_name}
            else:
                ip_pool.add(name=pool_name, ranges=ip_range)
                return {'step': 'ip_pool', 'success': True, 'action': 'created', 'pool_name': pool_name}
                
        except Exception as e:
            logger.error(f"IP pool configuration failed: {str(e)}")
            return {'step': 'ip_pool', 'success': False, 'error': str(e)}
    
    def _configure_wireless_interface(self, api, ssid: str) -> Dict:
        """Configure wireless interface."""
        try:
            wireless = api.get_resource('/interface/wireless')
            interfaces = wireless.get()
            
            if interfaces:
                wireless.set(
                    id=interfaces[0].get('.id'),
                    ssid=ssid,
                    disabled='no'
                )
                return {'step': 'wireless_interface', 'success': True, 'action': 'updated', 'ssid': ssid}
            else:
                wireless.add(
                    name="wlan1",
                    ssid=ssid,
                    mode="ap-bridge",
                    band="2ghz-b/g/n",
                    disabled='no'
                )
                return {'step': 'wireless_interface', 'success': True, 'action': 'created', 'ssid': ssid}
                
        except Exception as e:
            logger.error(f"Wireless interface configuration failed: {str(e)}")
            return {'step': 'wireless_interface', 'success': False, 'error': str(e)}
    
    def _configure_hotspot_server(self, api, ssid: str, redirect_url: str = None) -> Dict:
        """Configure hotspot server."""
        try:
            hotspot = api.get_resource('/ip/hotspot')
            servers = hotspot.get()
            
            hotspot_server_config = {
                'name': ssid,
                'interface': 'bridge',
                'address-pool': 'hotspot-pool',
                'profile': 'default',
                'disabled': 'no'
            }
            
            if redirect_url:
                hotspot_server_config['login-by'] = 'http-chap'
            
            if servers:
                hotspot.set(id=servers[0].get('.id'), **hotspot_server_config)
                return {'step': 'hotspot_server', 'success': True, 'action': 'updated'}
            else:
                hotspot.add(**hotspot_server_config)
                return {'step': 'hotspot_server', 'success': True, 'action': 'created'}
                
        except Exception as e:
            logger.error(f"Hotspot server configuration failed: {str(e)}")
            return {'step': 'hotspot_server', 'success': False, 'error': str(e)}
    
    def _configure_hotspot_profile(self, api, bandwidth_limit: str, session_timeout: int, welcome_message: str = None) -> Dict:
        """Configure hotspot profile."""
        try:
            profile = api.get_resource('/ip/hotspot/profile')
            profiles = profile.get(name='default')
            
            profile_config = {
                'name': 'default',
                'login-by': 'mac,http-chap,trial',
                'rate-limit': bandwidth_limit,
                'session-timeout': f'{session_timeout}m'
            }
            
            if welcome_message:
                profile_config['html-directory'] = 'hotspot'
            
            if profiles:
                profile.set(id=profiles[0].get('.id'), **profile_config)
                return {'step': 'hotspot_profile', 'success': True, 'action': 'updated'}
            else:
                profile.add(**profile_config)
                return {'step': 'hotspot_profile', 'success': True, 'action': 'created'}
                
        except Exception as e:
            logger.error(f"Hotspot profile configuration failed: {str(e)}")
            return {'step': 'hotspot_profile', 'success': False, 'error': str(e)}
    
    def _configure_user_profiles(self, api, max_users: int, bandwidth_limit: str) -> Dict:
        """Configure user profiles."""
        try:
            user_profile = api.get_resource('/ip/hotspot/user/profile')
            default_profile = user_profile.get(name='default')
            
            profile_config = {
                'name': 'default',
                'rate-limit': bandwidth_limit,
                'shared-users': str(max_users)
            }
            
            if default_profile:
                user_profile.set(id=default_profile[0].get('.id'), **profile_config)
            else:
                user_profile.add(**profile_config)
                
            return {'step': 'user_profiles', 'success': True, 'action': 'configured'}
            
        except Exception as e:
            logger.error(f"User profiles configuration failed: {str(e)}")
            return {'step': 'user_profiles', 'success': False, 'error': str(e)}
    
    def _configure_hotspot_firewall(self, api) -> Dict:
        """Configure basic firewall rules for hotspot."""
        try:
            firewall = api.get_resource('/ip/firewall/filter')
            
            rules = [
                {
                    'chain': 'input',
                    'protocol': 'tcp',
                    'dst-port': '80,443',
                    'action': 'accept',
                    'comment': 'Hotspot HTTP/HTTPS'
                },
                {
                    'chain': 'input', 
                    'protocol': 'udp',
                    'dst-port': '53',
                    'action': 'accept',
                    'comment': 'Hotspot DNS'
                }
            ]
            
            for rule in rules:
                firewall.add(**rule)
            
            return {'step': 'hotspot_firewall', 'success': True, 'action': 'configured'}
            
        except Exception as e:
            logger.error(f"Hotspot firewall configuration failed: {str(e)}")
            return {'step': 'hotspot_firewall', 'success': False, 'error': str(e)}
    
    def _configure_pppoe_server(self, api, service_name: str, mtu: int) -> Dict:
        """Configure PPPoE server."""
        try:
            pppoe_server = api.get_resource('/interface/pppoe-server/server')
            servers = pppoe_server.get()
            
            server_config = {
                'service-name': service_name,
                'interface': 'bridge',
                'max-mtu': str(mtu),
                'max-mru': str(mtu),
                'disabled': 'no'
            }
            
            if servers:
                pppoe_server.set(id=servers[0].get('.id'), **server_config)
                return {'step': 'pppoe_server', 'success': True, 'action': 'updated'}
            else:
                pppoe_server.add(**server_config)
                return {'step': 'pppoe_server', 'success': True, 'action': 'created'}
                
        except Exception as e:
            logger.error(f"PPPoE server configuration failed: {str(e)}")
            return {'step': 'pppoe_server', 'success': False, 'error': str(e)}
    
    def _configure_ppp_profiles(self, api, bandwidth_limit: str, ip_pool_name: str) -> Dict:
        """Configure PPP profiles for PPPoE."""
        try:
            ppp_profile = api.get_resource('/ppp/profile')
            default_profile = ppp_profile.get(name='default')
            
            profile_config = {
                'name': 'default',
                'local-address': '192.168.101.1',
                'remote-address': ip_pool_name,
                'rate-limit': bandwidth_limit,
                'change-tcp-mss': 'yes'
            }
            
            if default_profile:
                ppp_profile.set(id=default_profile[0].get('.id'), **profile_config)
            else:
                ppp_profile.add(**profile_config)
            
            return {'step': 'ppp_profiles', 'success': True, 'action': 'configured'}
            
        except Exception as e:
            logger.error(f"PPP profiles configuration failed: {str(e)}")
            return {'step': 'ppp_profiles', 'success': False, 'error': str(e)}
    
    def _configure_pppoe_secrets(self, api) -> Dict:
        """Configure example PPPoE user secrets."""
        try:
            ppp_secret = api.get_resource('/ppp/secret')
            
            # Use keyword arguments to avoid positional argument error
            ppp_secret.add(
                name='testuser',
                password='testpass123',
                service='pppoe',
                profile='default',
                remote_address='192.168.101.10'
            )
            
            return {'step': 'pppoe_secrets', 'success': True, 'action': 'created'}
            
        except Exception as e:
            logger.error(f"PPPoE secrets configuration failed: {str(e)}")
            return {'step': 'pppoe_secrets', 'success': False, 'error': str(e)}
    
    def _validate_hotspot_parameters(self, ssid: str, bandwidth_limit: str, session_timeout: int, max_users: int) -> list:
        """Validate hotspot configuration parameters."""
        errors = []
        
        if not ssid or len(ssid.strip()) == 0:
            errors.append("SSID cannot be empty")
        elif len(ssid) > 32:
            errors.append("SSID cannot exceed 32 characters")
        
        if not bandwidth_limit:
            errors.append("Bandwidth limit cannot be empty")
        elif not re.match(r'^\d+[KM]/\d+[KM]$', bandwidth_limit):
            errors.append("Bandwidth limit must be in format like '10M/10M'")
        
        if session_timeout < 1 or session_timeout > 1440:
            errors.append("Session timeout must be between 1 and 1440 minutes")
        
        if max_users < 1 or max_users > 1000:
            errors.append("Max users must be between 1 and 1000")
        
        return errors
    
    def _extract_system_info(self, system_info: Dict) -> Dict:
        """Extract and format system information."""
        return {
            'model': system_info.get('board-name', 'Unknown'),
            'version': system_info.get('version', 'Unknown'),
            'architecture': system_info.get('architecture', 'Unknown'),
            'cpu_load': system_info.get('cpu-load', 'Unknown'),
            'uptime': system_info.get('uptime', 'Unknown'),
            'free_memory': system_info.get('free-memory', 'Unknown'),
            'total_memory': system_info.get('total-memory', 'Unknown'),
            'cpu_count': system_info.get('cpu-count', '1'),
            'platform': system_info.get('platform', 'Unknown')
        }
    
    def _determine_capabilities(self, system_info: Dict) -> Dict:
        """Determine router capabilities based on system information."""
        capabilities = {
            'hotspot_support': True,
            'pppoe_support': True,
            'wireless_support': False,
            'advanced_qos': False,
            'vlan_support': True,
            'bridge_support': True,
            'advanced_routing': False
        }
        
        model = system_info.get('board-name', '').lower()
        
        # Check for wireless capabilities
        wireless_indicators = ['rb', 'sxt', 'lhg', 'wif', 'audience', 'cap', 'wap']
        if any(indicator in model for indicator in wireless_indicators):
            capabilities['wireless_support'] = True
        
        # Check for advanced features
        advanced_indicators = ['ccr', 'rb4011', 'rb5009', 'chateau', 'ltap', 'rb1100']
        if any(indicator in model for indicator in advanced_indicators):
            capabilities['advanced_qos'] = True
            capabilities['advanced_routing'] = True
        
        return capabilities
    
    def _get_additional_router_info(self, api, test_results: Dict):
        """Get additional router information."""
        try:
            interfaces = api.get_resource('/interface')
            interface_list = interfaces.get()
            test_results['interface_count'] = len(interface_list)
            
            try:
                wireless = api.get_resource('/interface/wireless')
                wireless_list = wireless.get()
                test_results['wireless_interfaces'] = len(wireless_list)
            except:
                test_results['wireless_interfaces'] = 0
            
            try:
                hotspot_servers = api.get_resource('/ip/hotspot')
                test_results['hotspot_configured'] = len(hotspot_servers.get()) > 0
            except:
                test_results['hotspot_configured'] = False
            
            try:
                pppoe_servers = api.get_resource('/interface/pppoe-server/server')
                test_results['pppoe_configured'] = len(pppoe_servers.get()) > 0
            except:
                test_results['pppoe_configured'] = False
                
        except Exception as e:
            logger.warning(f"Could not get additional router info: {str(e)}")
    
    def _generate_recommendations(self, test_results: Dict):
        """Generate recommendations based on test results."""
        if not test_results['system_access']:
            return
        
        capabilities = test_results.get('capabilities', {})
        
        if capabilities.get('wireless_support') and not test_results.get('hotspot_configured'):
            test_results['recommendations'].append("Router supports wireless - consider configuring hotspot")
        
        if capabilities.get('pppoe_support') and not test_results.get('pppoe_configured'):
            test_results['recommendations'].append("Router supports PPPoE - consider configuring PPPoE server")
        
        if test_results.get('response_time', 0) > 2.0:
            test_results['recommendations'].append("High response time detected - check network latency")
    
    def get_router_status(self) -> Dict:
        """
        Get comprehensive router status and statistics.
        
        Returns:
            dict: Router status information
        """
        try:
            success, message, api = self.connect()
            if not success:
                return {
                    'online': False,
                    'error': message,
                    'timestamp': self._get_current_timestamp()
                }
            
            status_info = {
                'online': True,
                'timestamp': self._get_current_timestamp(),
                'system': {},
                'interfaces': [],
                'resources': {},
                'services': {}
            }
            
            # Get system resource information
            system_resource = api.get_resource('/system/resource')
            system_info = system_resource.get()
            if system_info:
                status_info['system'] = self._extract_system_info(system_info[0])
            
            # Get interface information
            interfaces = api.get_resource('/interface')
            interface_list = interfaces.get()
            for interface in interface_list[:10]:  # Limit to first 10 interfaces
                status_info['interfaces'].append({
                    'name': interface.get('name'),
                    'type': interface.get('type'),
                    'running': interface.get('running') == 'true',
                    'rx_bytes': interface.get('rx-byte'),
                    'tx_bytes': interface.get('tx-byte')
                })
            
            # Get resource usage
            status_info['resources'] = {
                'cpu_load': system_info[0].get('cpu-load') if system_info else 'Unknown',
                'memory_usage': self._calculate_memory_usage(system_info[0]) if system_info else 'Unknown',
                'uptime': system_info[0].get('uptime') if system_info else 'Unknown'
            }
            
            # Get active services count
            try:
                hotspot_active = api.get_resource('/ip/hotspot/active')
                status_info['services']['hotspot_users'] = len(hotspot_active.get())
            except:
                status_info['services']['hotspot_users'] = 0
            
            try:
                pppoe_active = api.get_resource('/ppp/active')
                status_info['services']['pppoe_users'] = len(pppoe_active.get())
            except:
                status_info['services']['pppoe_users'] = 0
            
            return status_info
            
        except Exception as e:
            logger.error(f"Failed to get router status for {self.ip}: {str(e)}")
            return {
                'online': False,
                'error': str(e),
                'timestamp': self._get_current_timestamp()
            }
        finally:
            if self.api_pool:
                try:
                    self.api_pool.disconnect()
                except:
                    pass
    
    def _calculate_memory_usage(self, system_info: Dict) -> str:
        """Calculate memory usage percentage."""
        try:
            free_memory = int(system_info.get('free-memory', 0))
            total_memory = int(system_info.get('total-memory', 1))
            usage_percent = ((total_memory - free_memory) / total_memory) * 100
            return f"{usage_percent:.1f}%"
        except (ValueError, ZeroDivisionError):
            return "Unknown"
    
    def disconnect(self):
        """Clean up connections."""
        if self.api_pool:
            try:
                self.api_pool.disconnect()
                logger.debug(f"Disconnected from router {self.ip}")
            except Exception as e:
                logger.warning(f"Error disconnecting from router {self.ip}: {str(e)}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with proper cleanup."""
        self.disconnect()


HOTSPOT_OWNED_TAG = "surfzone-hotspot"

# Object types confirmed this session, via real RouterOS API rejections, to
# not support `comment` on .add()/.set() at all on this device's RouterOS
# build. Checked proactively so we don't round-trip a doomed write for
# these; anything not in this set still goes through the self-heal below.
_NO_COMMENT_SUPPORT_PATHS = {'/ip/hotspot/profile', '/ip/hotspot', '/ip/hotspot/user/profile'}

_UNKNOWN_PARAM_RE = re.compile(r'unknown parameter ([\w-]+)')

# Fields that carry real functionality - if RouterOS rejects any of these,
# that's a stop-and-report condition, never something to silently drop.
_FUNCTIONAL_FIELDS = {
    'name', 'interface', 'address-pool', 'profile', 'login-by',
    'rate-limit', 'shared-users', 'session-timeout',
    'protocol', 'dst-port', 'action', 'chain',
    'mode', 'security-profile', 'ssid',
}


def _comment_known_supported(api, path):
    """
    Best-effort, read-only signal from an existing row: True if some row of
    this type already carries a non-empty comment (conclusive - RouterOS
    wouldn't have accepted it otherwise). Returns None when inconclusive
    (no row has one set) - absence doesn't prove the field is invalid, only
    that it's unused, so this is a hint, not a verdict.
    """
    try:
        rows = api.get_resource(path).get() or []
        if any(r.get('comment') for r in rows):
            return True
    except Exception:
        pass
    return None


def _write(api, path, method, kwargs):
    """
    Issue one .add()/.set() call, schema-aware for `comment`:
    - if this path is already known (this session) not to support comment,
      it's dropped before ever attempting the call.
    - otherwise, if RouterOS rejects the call specifically with "unknown
      parameter comment", retry once without it - a self-heal for object
      types whose comment support hasn't been seen yet.
    - a rejection naming any other parameter (a functional field) is not
      caught here - it propagates to the caller unchanged, which is the
      stop-and-report path.
    Returns the kwargs dict actually sent (post-heal), so the caller can
    report accurately what was written.
    """
    if path in _NO_COMMENT_SUPPORT_PATHS and 'comment' in kwargs:
        kwargs = {k: v for k, v in kwargs.items() if k != 'comment'}

    try:
        getattr(api.get_resource(path), method)(**kwargs)
        return kwargs
    except Exception as e:
        m = _UNKNOWN_PARAM_RE.search(str(e))
        bad_param = m.group(1) if m else None
        if bad_param == 'comment' and 'comment' in kwargs:
            healed_kwargs = {k: v for k, v in kwargs.items() if k != 'comment'}
            getattr(api.get_resource(path), method)(**healed_kwargs)
            return healed_kwargs
        if bad_param and bad_param in _FUNCTIONAL_FIELDS:
            raise RuntimeError(
                f"{path}.{method}: RouterOS rejected functional field '{bad_param}' - {e}"
            ) from e
        raise


# Fields RouterOS reports back reordered/reformatted rather than verbatim,
# so a naive string compare would flag them as perpetually drifted even
# when nothing actually changed. login-by is a comma-separated set (RouterOS
# stores/returns it in its own canonical order, e.g. "mac,http-chap" no
# matter what order it was sent in) - compared as a set, not a string.
_UNORDERED_SET_FIELDS = {'login-by'}

# ssid gets the same "don't re-fire cosmetically" care, but NOT via the
# comma-split/unordered-set treatment above: ssid is a single opaque value,
# not a set, and an SSID is technically free to contain a literal comma
# ("Cafe,Free-WiFi" vs "Free-WiFi,Cafe" would then compare equal though
# they're different SSIDs). The only cosmetic variance a scalar RouterOS
# string field actually exhibits is incidental whitespace, so it's
# compared trimmed instead - same intent (skip spurious SETs) without the
# false-equality risk.
_TRIMMED_FIELDS = {'ssid'}


def _values_equal(key, existing_val, desired_val):
    if key in _UNORDERED_SET_FIELDS:
        existing_set = {x.strip() for x in str(existing_val).split(',') if x.strip()}
        desired_set = {x.strip() for x in str(desired_val).split(',') if x.strip()}
        return existing_set == desired_set
    if key in _TRIMMED_FIELDS:
        return str(existing_val).strip() == str(desired_val).strip()
    return str(existing_val) == str(desired_val)


def _plan_reconcile(changes, unchanged, failed, dry_run, api, path, existing_row, desired_attrs, label):
    """
    Shared get-by-name/comment -> set-else-add primitive, dry-run aware and
    schema-aware for `comment` (see _write()).

    existing_row: the matched row dict, or None if nothing matched.
    desired_attrs: dict of RouterOS field names (dashed, as the API expects)
    to desired string values. Only keys present here are ever compared/set -
    fields not listed are left untouched on an existing row.

    dry_run=True: appends the "CREATE ..."/"SET ..." description to `changes`
    as a preview (pre-emptively drops comment in the preview too, if this
    path is already known unsupported) - no write is ever issued.
    dry_run=False: only appends to `changes` AFTER the .add()/.set() call
    returns successfully, reflecting exactly what was sent (comment may have
    been silently dropped - noted in the description). A failure on a
    functional field is appended to `failed` and re-raised so the caller
    stops rather than pressing on to later steps.
    Appends to `unchanged` when the row already matches (no write needed).
    """
    if existing_row is None:
        planned = dict(desired_attrs)
        if dry_run:
            if path in _NO_COMMENT_SUPPORT_PATHS and 'comment' in planned:
                del planned['comment']
            desc = f"CREATE {path} " + " ".join(f"{k}={v}" for k, v in planned.items())
            changes.append(desc)
            return
        try:
            sent = _write(api, path, 'add', planned)
        except Exception as e:
            desc = f"CREATE {path} " + " ".join(f"{k}={v}" for k, v in planned.items())
            failed.append(f"{desc} -> ERROR: {e}")
            raise
        note = " (comment dropped - unsupported on this object)" if 'comment' in planned and 'comment' not in sent else ""
        changes.append(f"CREATE {path} " + " ".join(f"{k}={v}" for k, v in sent.items()) + note)
        return

    drifted = {
        k: v for k, v in desired_attrs.items()
        if not _values_equal(k, existing_row.get(k, ''), v)
    }
    if not drifted:
        unchanged.append(f"{path} ({label}) already correct")
        return

    if dry_run:
        planned = dict(drifted)
        if path in _NO_COMMENT_SUPPORT_PATHS and 'comment' in planned:
            del planned['comment']
        if not planned:
            unchanged.append(f"{path} ({label}) already correct (comment unsupported, ignored)")
            return
        desc = f"SET {path} id={existing_row.get('id')} " + " ".join(f"{k}={v}" for k, v in planned.items())
        changes.append(desc)
        return

    try:
        sent = _write(api, path, 'set', {'id': existing_row['id'], **drifted})
    except Exception as e:
        desc = f"SET {path} id={existing_row.get('id')} " + " ".join(f"{k}={v}" for k, v in drifted.items())
        failed.append(f"{desc} -> ERROR: {e}")
        raise
    sent_no_id = {k: v for k, v in sent.items() if k != 'id'}
    if not sent_no_id:
        unchanged.append(f"{path} ({label}) already correct (comment unsupported, ignored)")
        return
    note = " (comment dropped - unsupported on this object)" if 'comment' in drifted and 'comment' not in sent_no_id else ""
    changes.append(
        f"SET {path} id={existing_row.get('id')} " + " ".join(f"{k}={v}" for k, v in sent_no_id.items()) + note
    )


def prepare_hotspot_service(router, dry_run: bool = False) -> Tuple[bool, str, Dict]:
    """
    Idempotent, router-scoped routine that brings a factory-fresh MikroTik to
    a working, stock-login hotspot: adopts/creates the bridge subnet, an IP
    pool and DHCP server bound to it, the missing NAT masquerade out ether1
    (the actual internet-path fix), a hotspot server + named server-profile
    (surfzone-hotspot), a baseline per-user profile (default), and the two
    firewall input-accepts hotspot needs. No walled-garden/redirect here -
    that's stage 0b.

    Every object this routine owns is tagged comment="surfzone-hotspot" and
    matched by name/comment (or, for NAT/firewall, by functional equivalence
    too) before any add, so re-running it is a no-op once state matches.
    Deliberately does not call _configure_hotspot_firewall() (duplicates on
    rerun) or anything from configure_pppoe() (test-user secret, wrong app).

    Safety: refuses to run at all if ether1 is a bridge port (would mean the
    WAN path is bridged into the LAN) - never touches ether1 or wg-vultr
    other than naming ether1 as the NAT out-interface.

    dry_run=True: connects and reads only (`.get()` calls exclusively - no
    write command is ever constructed), returns the exact ordered list of
    changes that would be made without sending any of them.
    dry_run=False: same plan, each CREATE/SET is actually applied.

    Returns (success, message, details) where details['changes'] is the
    ordered "CREATE/SET <path> <key=value ...>" list and
    details['unchanged'] lists what was already correct.

    Connection note: this deliberately does NOT go through
    MikroTikConnector.connect() / ConnectionPoolManager.get_pool() - that
    path currently passes use_ssl/ssl_verify/timeout/max_connections kwargs
    that the installed routeros_api version's RouterOsApiPool.__init__()
    rejects (a pre-existing bug affecting configure_hotspot(),
    configure_pppoe() and HotspotConfiguration.apply_configuration() too,
    not introduced here). Uses the same plain RouterOsApiPool(...,
    plaintext_login=True) construction already proven to work elsewhere in
    this codebase (network_management/services/hotspot_provisioning.py,
    RouterStatsView).
    """
    changes: List[str] = []
    unchanged: List[str] = []
    failed: List[str] = []
    empty_details = {'changes': changes, 'unchanged': unchanged, 'failed': failed}
    TAG = HOTSPOT_OWNED_TAG

    api_pool = RouterOsApiPool(
        router.ip,
        username=router.username,
        password=router.password,
        port=router.port,
        plaintext_login=True,
    )
    try:
        api = api_pool.get_api()
    except Exception as e:
        return False, f"{type(e).__name__}: {e}", empty_details

    try:
        # --- Safety gate: never touch a router where ether1 (WAN) is bridged ---
        bridge_ports = api.get_resource('/interface/bridge/port').get() or []
        if any(p.get('interface') == 'ether1' for p in bridge_ports):
            msg = (
                "ether1 is a bridge port on this router - refusing to configure "
                "hotspot (this would touch the WAN path)"
            )
            logger.error(f"prepare_hotspot_service aborted for {router.ip}: {msg}")
            return False, msg, empty_details

        # --- Pull ssid/bandwidth/session-timeout/max-users: per-router
        # HotspotConfiguration row where present, else env defaults ---
        defaults = MikroTikConfig.get_hotspot_defaults()
        ssid = defaults['default_ssid']
        bandwidth_limit = defaults['bandwidth_limit']
        session_timeout = defaults['session_timeout']
        max_users = defaults['max_users']
        configured_dns_servers = None

        if DJANGO_AVAILABLE and getattr(router, 'id', None):
            try:
                from network_management.models.router_management_model import HotspotConfiguration
                config = HotspotConfiguration.objects.filter(router_id=router.id).first()
                if config:
                    ssid = config.ssid or ssid
                    bandwidth_limit = config.rate_limit or bandwidth_limit
                    session_timeout = config.session_timeout or session_timeout
                    max_users = config.max_users or max_users
                    configured_dns_servers = config.dns_servers or None
            except Exception as e:
                logger.warning(f"Could not load HotspotConfiguration for router {router.id}: {e}")

        # --- Step 1: hotspot interface + subnet - bridge only, adopt existing ---
        addresses = api.get_resource('/ip/address').get() or []
        bridge_addr = next((a for a in addresses if a.get('interface') == 'bridge'), None)

        if bridge_addr and bridge_addr.get('address'):
            bridge_cidr = bridge_addr['address']
            unchanged.append(f"/ip/address bridge already has {bridge_cidr}")
        else:
            bridge_cidr = "192.168.88.1/24"
            changes.append(f"CREATE /ip/address address={bridge_cidr} interface=bridge comment={TAG}")
            if not dry_run:
                api.get_resource('/ip/address').add(address=bridge_cidr, interface='bridge', comment=TAG)

        iface = ipaddress.ip_interface(bridge_cidr)
        network = iface.network
        gateway_ip = iface.ip

        # --- Step 2: IP pool in that subnet - derive range, reconcile default-dhcp
        # rather than creating a second, mismatched pool ---
        hosts = [h for h in network.hosts() if h != gateway_ip]
        derived_range = f"{hosts[0]}-{hosts[-1]}" if hosts else None

        def _range_in_network(ranges_str):
            try:
                first, last = ranges_str.split('-')
                return (
                    ipaddress.ip_address(first.strip()) in network
                    and ipaddress.ip_address(last.strip()) in network
                )
            except Exception:
                return False

        pools = api.get_resource('/ip/pool').get() or []
        pool_row = next((p for p in pools if p.get('name') == 'default-dhcp'), None)
        if pool_row is None:
            pool_row = next((p for p in pools if p.get('comment') == TAG), None)

        if pool_row is not None and _range_in_network(pool_row.get('ranges', '')):
            # Already in the right subnet - only claim ownership via comment,
            # never rewrite a range that's already sane.
            pool_name = pool_row['name']
            _plan_reconcile(
                changes, unchanged, failed, dry_run, api, '/ip/pool', pool_row,
                {'comment': TAG}, pool_name,
            )
        elif pool_row is not None:
            pool_name = pool_row['name']
            _plan_reconcile(
                changes, unchanged, failed, dry_run, api, '/ip/pool', pool_row,
                {'ranges': derived_range, 'comment': TAG}, pool_name,
            )
        else:
            pool_name = 'surfzone-hotspot-pool'
            _plan_reconcile(
                changes, unchanged, failed, dry_run, api, '/ip/pool', None,
                {'name': pool_name, 'ranges': derived_range, 'comment': TAG}, pool_name,
            )

        # --- Step 3: DHCP server on bridge, bound to that pool - reuse existing ---
        dhcp_servers = api.get_resource('/ip/dhcp-server').get() or []
        dhcp_row = next((d for d in dhcp_servers if d.get('interface') == 'bridge'), None)

        if dhcp_row is not None:
            dhcp_name = dhcp_row.get('name')
            _plan_reconcile(
                changes, unchanged, failed, dry_run, api, '/ip/dhcp-server', dhcp_row,
                {'address-pool': pool_name, 'comment': TAG}, dhcp_name,
            )
        else:
            dhcp_name = 'surfzone-hotspot-dhcp'
            _plan_reconcile(
                changes, unchanged, failed, dry_run, api, '/ip/dhcp-server', None,
                {
                    'name': dhcp_name, 'interface': 'bridge', 'address-pool': pool_name,
                    'lease-time': '1d', 'disabled': 'no', 'comment': TAG,
                },
                dhcp_name,
            )

        # DHCP network entry (gateway/dns) for the subnet - without it the
        # server hands out an address but no gateway, so it isn't actually a
        # working hotspot yet. dns-server is adopt-if-set, same as the pool
        # range: never overwrite a value that's already there, only fill it
        # in when genuinely absent - and fall back to the hotspot gateway
        # itself (not a public resolver) so a router with nothing configured
        # still resolves locally.
        dhcp_networks = api.get_resource('/ip/dhcp-server/network').get() or []

        def _same_subnet(row):
            try:
                return ipaddress.ip_network(row.get('address', ''), strict=False) == network
            except Exception:
                return False

        net_row = next((n for n in dhcp_networks if _same_subnet(n)), None)
        net_desired = {'address': str(network), 'gateway': str(gateway_ip), 'comment': TAG}
        if not (net_row or {}).get('dns-server'):
            net_desired['dns-server'] = configured_dns_servers or str(gateway_ip)

        _plan_reconcile(
            changes, unchanged, failed, dry_run, api, '/ip/dhcp-server/network', net_row,
            net_desired, str(network),
        )

        # --- Step 4: NAT masquerade for the hotspot subnet out ether1. Only
        # create the explicit tagged rule if nothing already gives this
        # subnet an adequate masquerade path: an enabled srcnat/masquerade
        # rule whose src-address covers the subnet (or has none, i.e.
        # applies to everything), reachable via ether1 either directly
        # (out-interface=ether1) or through an interface list ether1 is a
        # member of (out-interface-list=<list>), or with neither
        # out-interface nor out-interface-list set (applies to all
        # interfaces). Any ambiguity (unparseable src-address, etc.) is
        # treated as NOT covered, so we create rather than risk a false
        # "already fine". ---
        list_members = api.get_resource('/interface/list/member').get() or []
        ether1_lists = {
            m.get('list') for m in list_members
            if m.get('interface') == 'ether1' and m.get('disabled', 'false') != 'true'
        }

        def _rule_covers_subnet(rule):
            if rule.get('chain') != 'srcnat' or rule.get('action') != 'masquerade':
                return False
            if rule.get('disabled') == 'true':
                return False
            out_iface = rule.get('out-interface', '')
            out_iface_list = rule.get('out-interface-list', '')
            if out_iface and out_iface != 'ether1':
                return False
            if out_iface_list and out_iface_list not in ether1_lists:
                return False
            src = rule.get('src-address', '')
            if not src:
                return True
            try:
                src_net = ipaddress.ip_network(src, strict=False)
                return network == src_net or network.subnet_of(src_net)
            except Exception:
                return False

        nat_rules = api.get_resource('/ip/firewall/nat').get() or []
        covering_rule = next((r for r in nat_rules if _rule_covers_subnet(r)), None)

        if covering_rule is not None:
            unchanged.append(
                f"/ip/firewall/nat masquerade for {network} already covered by existing rule "
                f"id={covering_rule.get('id')} comment={covering_rule.get('comment', '')!r}"
            )
        else:
            nat_row = next((r for r in nat_rules if r.get('comment') == TAG), None)
            _plan_reconcile(
                changes, unchanged, failed, dry_run, api, '/ip/firewall/nat', nat_row,
                {
                    'chain': 'srcnat', 'action': 'masquerade', 'src-address': str(network),
                    'out-interface': 'ether1', 'comment': TAG,
                },
                f"masquerade {network} -> ether1",
            )

        # --- Step 5/6: hotspot server on bridge + named server-profile ---
        hotspot_profiles = api.get_resource('/ip/hotspot/profile').get() or []
        profile_row = next((p for p in hotspot_profiles if p.get('name') == 'surfzone-hotspot'), None)
        _plan_reconcile(
            changes, unchanged, failed, dry_run, api, '/ip/hotspot/profile', profile_row,
            {
                # rate-limit/session-timeout/comment are NOT valid fields on
                # the server-profile object on this RouterOS version -
                # confirmed by two real API rejections. rate-limit and
                # session-timeout live on /ip/hotspot/user/profile instead
                # (step 7, below). No comment support here at all, so this
                # object is owned/matched by name alone.
                'name': 'surfzone-hotspot', 'login-by': 'http-chap,mac',
            },
            'surfzone-hotspot',
        )

        hotspot_servers = api.get_resource('/ip/hotspot').get() or []
        server_row = next(
            (h for h in hotspot_servers if h.get('interface') == 'bridge' or h.get('comment') == TAG),
            None,
        )
        _plan_reconcile(
            changes, unchanged, failed, dry_run, api, '/ip/hotspot', server_row,
            {
                'name': ssid, 'interface': 'bridge', 'address-pool': pool_name,
                'profile': 'surfzone-hotspot', 'disabled': 'no', 'comment': TAG,
            },
            ssid,
        )

        # --- Step 7: per-user profile baseline "default" - placeholder until
        # Stage A adds plan-named profiles. Carries session-timeout too -
        # that field lives here, not on the server-profile (step 5/6). ---
        user_profiles = api.get_resource('/ip/hotspot/user/profile').get() or []
        user_profile_row = next((p for p in user_profiles if p.get('name') == 'default'), None)
        _plan_reconcile(
            changes, unchanged, failed, dry_run, api, '/ip/hotspot/user/profile', user_profile_row,
            {
                'name': 'default', 'rate-limit': bandwidth_limit,
                'shared-users': str(max_users), 'session-timeout': f'{session_timeout}m',
                'comment': TAG,
            },
            'default',
        )

        # --- Step 8: firewall input-accepts hotspot needs - matched by
        # (chain, protocol, dst-port, action) so a pre-existing, differently
        # -commented equivalent rule is recognized too, not just our own tag ---
        firewall_rules = api.get_resource('/ip/firewall/filter').get() or []
        needed_rules = [
            {'chain': 'input', 'protocol': 'udp', 'dst-port': '53', 'action': 'accept', 'comment': TAG},
            {'chain': 'input', 'protocol': 'tcp', 'dst-port': '80,443', 'action': 'accept', 'comment': TAG},
        ]
        for rule in needed_rules:
            match_keys = ('chain', 'protocol', 'dst-port', 'action')
            existing = next(
                (
                    r for r in firewall_rules
                    if all(r.get(k) == rule[k] for k in match_keys)
                ),
                None,
            )
            label = f"{rule['protocol']}/{rule['dst-port']} accept"
            _plan_reconcile(
                changes, unchanged, failed, dry_run, api, '/ip/firewall/filter', existing, rule, label,
            )

        # --- Step 9: open security-profile "surfzone-open" (mode=none - no
        # WPA/authentication required to associate). Reconciled by name
        # only, like the other named profiles above. Deliberately does not
        # touch whatever security-profile already exists (e.g. "default"
        # WPA2) - that stays in place, untouched, as a fallback. ---
        security_profiles = api.get_resource('/interface/wireless/security-profiles').get() or []
        open_profile_row = next((p for p in security_profiles if p.get('name') == 'surfzone-open'), None)
        _plan_reconcile(
            changes, unchanged, failed, dry_run, api, '/interface/wireless/security-profiles', open_profile_row,
            {'name': 'surfzone-open', 'mode': 'none'},
            'surfzone-open',
        )

        # --- Step 10: wireless interface - security-profile + SSID -
        # selected by NAME only, never by index or list position. Acts only
        # on the one configured interface (WIRELESS_IFACE_NAME); never
        # creates a wireless interface (that's hardware-backed, not
        # something to fabricate via config), and any other wireless
        # interface present is left untouched and reported explicitly
        # rather than silently ignored. ---
        WIRELESS_IFACE_NAME = 'wlan1'
        wireless_ifaces = api.get_resource('/interface/wireless').get() or []
        target_wireless = next(
            (w for w in wireless_ifaces if w.get('name') == WIRELESS_IFACE_NAME), None
        )

        if target_wireless is not None:
            _plan_reconcile(
                changes, unchanged, failed, dry_run, api, '/interface/wireless', target_wireless,
                {'security-profile': 'surfzone-open', 'ssid': ssid}, WIRELESS_IFACE_NAME,
            )
        else:
            unchanged.append(
                f"/interface/wireless: no interface named {WIRELESS_IFACE_NAME!r} found - skipped, nothing touched"
            )

        for w in wireless_ifaces:
            if w.get('name') != WIRELESS_IFACE_NAME:
                unchanged.append(
                    f"/interface/wireless {w.get('name')}: not the configured interface - left untouched"
                )

        # --- Step 11: walled-garden dst-host allows for the buy page and
        # its only external dependency (Google Fonts). Matched per-host on
        # dst-host so re-runs never duplicate. Comment support on this menu
        # is unconfirmed - _write()'s self-heal drops it automatically if
        # RouterOS rejects it, same as the other /ip/hotspot/* objects.
        # Deliberately excludes OS captive-probe domains (apple/gstatic
        # connectivity-check/msftconnecttest) - those must stay interceptable
        # for the phone's auto-login-popup to fire at all. ---
        WALLED_GARDEN_HOSTS = [
            'surfzone.stormclouds.co.ke',
            'fonts.googleapis.com',
            'fonts.gstatic.com',
        ]
        walled_garden_rows = api.get_resource('/ip/hotspot/walled-garden').get() or []
        for host in WALLED_GARDEN_HOSTS:
            existing = next((w for w in walled_garden_rows if w.get('dst-host') == host), None)
            _plan_reconcile(
                changes, unchanged, failed, dry_run, api, '/ip/hotspot/walled-garden', existing,
                {'dst-host': host, 'action': 'allow', 'comment': TAG},
                host,
            )

        overall_message = (
            f"{len(changes)} change(s) {'would be' if dry_run else 'were'} applied, "
            f"{len(unchanged)} item(s) already correct"
        )
        return True, overall_message, {'changes': changes, 'unchanged': unchanged, 'failed': failed}

    except Exception as e:
        logger.error(f"prepare_hotspot_service failed for {router.ip}: {e}")
        return False, f"prepare_hotspot_service failed: {e}", {'changes': changes, 'unchanged': unchanged, 'failed': failed}
    finally:
        try:
            api_pool.disconnect()
        except Exception:
            pass


# Only these characters are known-safe on RouterOS name fields (confirmed
# unmodified via a live probe against router 19: a raw space+mixed-case
# name round-tripped byte-for-byte). Everything else - commas, semicolons,
# quotes, control chars, none of which have been probed - is replaced
# rather than trusted.
_PLAN_NAME_UNSAFE_CHARS_RE = re.compile(r'[^A-Za-z0-9 _-]')
_WHITESPACE_RUN_RE = re.compile(r'\s+')
_PLAN_PROFILE_NAME_MAX_LEN = 60


def plan_to_profile_name(plan) -> str:
    """
    The ONE deterministic InternetPlan.name -> RouterOS profile-name
    mapping. push_plan_profile() (below) and
    hotspot_provisioning.provision_hotspot_user()'s `profile=` kwarg
    MUST both call this and only this - if either one derives the name
    any other way, a pushed profile and an activation's requested
    profile silently stop matching and hotspot users fall back to
    RouterOS's undocumented "profile not found" behavior instead of the
    plan's actual rate limits.

    Rule: keep [A-Za-z0-9 _-], replace anything else with '-', collapse
    whitespace runs to a single space, trim, cap at
    _PLAN_PROFILE_NAME_MAX_LEN chars (trimmed again after the cut, in
    case truncation lands mid-space/dash).
    """
    name = getattr(plan, 'name', '') or ''
    name = _PLAN_NAME_UNSAFE_CHARS_RE.sub('-', name)
    name = _WHITESPACE_RUN_RE.sub(' ', name).strip()
    name = name[:_PLAN_PROFILE_NAME_MAX_LEN].strip()
    return name or 'surfzone-plan'


# access_methods stores speed units as 'Mbps'/'Kbps'/'Gbps' (human-facing
# strings from the plan-editor UI); RouterOS rate-limit tokens want a bare
# numeric suffix instead ('M'/'k'/'G'). Concatenating the raw unit string
# ("10Mbps") would send RouterOS a value it doesn't recognize. Unrecognized
# or missing units fall back to 'M' - the same default access_methods
# itself uses for speed fields.
_SPEED_UNIT_TO_ROUTEROS_SUFFIX = {'mbps': 'M', 'kbps': 'k', 'gbps': 'G'}

# Product policy: a phone idle in someone's pocket should not silently keep
# accruing connected time. Fixed, not derived from any plan field.
HOTSPOT_PROFILE_IDLE_TIMEOUT = '5m'


def _routeros_rate_token(value, unit) -> str:
    suffix = _SPEED_UNIT_TO_ROUTEROS_SUFFIX.get(str(unit).strip().lower(), 'M')
    return f"{value}{suffix}"


_DURATION_UNIT_SECONDS = {
    's': 1, 'sec': 1, 'secs': 1, 'second': 1, 'seconds': 1,
    'm': 60, 'min': 60, 'mins': 60, 'minute': 60, 'minutes': 60,
    'h': 3600, 'hr': 3600, 'hrs': 3600, 'hour': 3600, 'hours': 3600,
    'd': 86400, 'day': 86400, 'days': 86400,
}


def _plan_hotspot_raw(plan) -> Dict:
    """
    Raw access_methods['hotspot'] dict, or {}. Deliberately bypasses
    Plan.get_technical_config(), which silently substitutes a default
    value/unit pair for any missing sub-field (e.g. {'value': '10', 'unit':
    'gb'} for a missing data_limit) - that default masks a genuinely-
    unconfigured plan as a real limit. Callers here need to tell "missing"
    apart from "explicitly set" so they can refuse to guess a number.
    """
    if plan is None:
        return {}
    return (getattr(plan, 'access_methods', None) or {}).get('hotspot') or {}


def plan_uptime_limit_seconds(plan) -> Optional[int]:
    """
    Connected-time allowance in seconds, from access_methods.hotspot.
    usage_limit (value/unit pair, same {'value', 'unit'} shape and
    'Unlimited' convention as data_limit). This is the field the rest of
    the app treats as a duration allowance - formatted via
    format_duration_display alongside validity_period, labelled "Usage
    Limit" in the plan editor, always expressed in Hours or 'Unlimited' in
    the admin UI's own presets (usageLimitPresets in
    ServiceManagement/Shared/constant.js). NOT validity_period, which is
    the calendar window the subscription itself expires on
    (service_operations.services.payment_activation._plan_duration_hours) -
    usage_limit is how much *connected* time the account gets to spend
    within that window.

    Shared by hotspot_provisioning.provision_hotspot_user() (limit-uptime
    on the user) and push_plan_profile() below (session-timeout on the
    profile) - both need the exact same allowance number.

    Returns None for "Unlimited" (no cap - caller must omit limit-uptime
    entirely, never write 0 or a large number) and also for a missing or
    unreadable value - same "don't guess" policy as the data_limit fix in
    hotspot_provisioning._plan_data_limit_bytes, logged either way so a
    misconfigured plan is visible rather than silently capped or uncapped.
    """
    usage_limit = _plan_hotspot_raw(plan).get('usage_limit')
    if not isinstance(usage_limit, dict) or not usage_limit.get('value') or not usage_limit.get('unit'):
        logger.warning(
            "Plan %s has no usable usage_limit under access_methods.hotspot; "
            "provisioning with no connected-time cap.",
            getattr(plan, 'id', 'unknown'),
        )
        return None

    value = usage_limit['value']
    unit = usage_limit['unit']

    if str(value).strip().lower() == 'unlimited' or str(unit).strip().lower() == 'unlimited':
        return None

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        logger.warning(
            "Unparseable usage_limit value %r on plan %s; provisioning with no connected-time cap.",
            value, getattr(plan, 'id', 'unknown'),
        )
        return None

    multiplier = _DURATION_UNIT_SECONDS.get(str(unit).strip().lower())
    if multiplier is None:
        logger.warning(
            "Unrecognized usage_limit unit %r on plan %s; provisioning with no connected-time cap.",
            unit, getattr(plan, 'id', 'unknown'),
        )
        return None

    return int(numeric_value * multiplier)


def push_plan_profile(plan, router, dry_run: bool = False) -> Tuple[bool, str, Dict]:
    """
    Idempotent, single-router push of one InternetPlan's hotspot rate
    limits onto RouterOS as a /ip/hotspot/user/profile. Reuses the same
    _plan_reconcile()/_write() machinery as prepare_hotspot_service()
    (schema-aware comment handling, functional-field-rejection stops the
    caller rather than silently dropping, dry-run preview support),
    matched by name via plan_to_profile_name(plan) - see that function's
    docstring for why this must be the only place that name is derived.

    Deliberately does NOT set a data cap here: limit_bytes_total is a
    per-user attribute applied at activation time
    (hotspot_provisioning.provision_hotspot_user), not a per-profile
    RouterOS field, so data_limit/data_unit from get_technical_config()
    are not used by this function.

    Field mapping, from plan.get_technical_config('hotspot'):
      rate-limit      = "{upload}{unit-suffix}/{download}{unit-suffix}"
                         (RouterOS convention: rx-rate/tx-rate, i.e. what
                         the router receives from the client / sends to
                         the client = upload/download)
      shared-users    = str(max_devices), falling back to 1 if unset/blank
      session-timeout = plan_uptime_limit_seconds(plan) (the plan's full
                         connected-time allowance, access_methods.hotspot.
                         usage_limit) with an 's' suffix - bounds a single
                         login to at most the plan's entire allowance.
                         This is a coarse, profile-wide bound only:
                         limit-uptime on the individual /ip/hotspot/user
                         entry (set in
                         hotspot_provisioning.provision_hotspot_user, which
                         also carries over unused time across repeat
                         purchases) is the real cumulative gate: RouterOS
                         disconnects once accumulated uptime reaches it,
                         same as this, whichever comes first. Falls back
                         to the legacy access_methods.hotspot.session_timeout
                         raw field (or 86400s) when usage_limit is
                         Unlimited/unreadable, since there's no allowance
                         to bound a single session against in that case.
      idle-timeout    = fixed 5 minutes (product policy, not derived from
                         any plan field - a phone idle in someone's pocket
                         should not keep counting as connected time).

    dry_run=True: connects and reads only, returns the planned
    CREATE/SET without writing. dry_run=False: applies it.
    """
    changes: List[str] = []
    unchanged: List[str] = []
    failed: List[str] = []
    empty_details = {'changes': changes, 'unchanged': unchanged, 'failed': failed}

    api_pool = RouterOsApiPool(
        router.ip,
        username=router.username,
        password=router.password,
        port=router.port,
        plaintext_login=True,
    )
    try:
        api = api_pool.get_api()
    except Exception as e:
        return False, f"{type(e).__name__}: {e}", empty_details

    try:
        profile_name = plan_to_profile_name(plan)
        config = plan.get_technical_config('hotspot')

        rate_limit = "{}/{}".format(
            _routeros_rate_token(config['upload_speed'], config.get('upload_unit', 'Mbps')),
            _routeros_rate_token(config['download_speed'], config.get('download_unit', 'Mbps')),
        )
        shared_users = str(config.get('max_devices') or 1)

        uptime_allowance_seconds = plan_uptime_limit_seconds(plan)
        if uptime_allowance_seconds is not None:
            session_timeout = f"{uptime_allowance_seconds}s"
        else:
            session_timeout = f"{config.get('session_timeout') or 86400}s"

        user_profiles = api.get_resource('/ip/hotspot/user/profile').get() or []
        existing = next((p for p in user_profiles if p.get('name') == profile_name), None)
        _plan_reconcile(
            changes, unchanged, failed, dry_run, api, '/ip/hotspot/user/profile', existing,
            {
                'name': profile_name, 'rate-limit': rate_limit,
                'shared-users': shared_users, 'session-timeout': session_timeout,
                'idle-timeout': HOTSPOT_PROFILE_IDLE_TIMEOUT,
            },
            profile_name,
        )

        overall_message = (
            f"{len(changes)} change(s) {'would be' if dry_run else 'were'} applied, "
            f"{len(unchanged)} item(s) already correct"
        )
        return True, overall_message, {'changes': changes, 'unchanged': unchanged, 'failed': failed}

    except Exception as e:
        logger.error(f"push_plan_profile failed for plan {getattr(plan, 'id', '?')} on {router.ip}: {e}")
        return False, f"push_plan_profile failed: {e}", {'changes': changes, 'unchanged': unchanged, 'failed': failed}
    finally:
        try:
            api_pool.disconnect()
        except Exception:
            pass


def push_pppoe_profile(plan, router, dry_run: bool = False) -> Tuple[bool, str, Dict]:
    """
    PPPoE counterpart to push_plan_profile() above - idempotent, single-
    router push of one InternetPlan's PPPoE rate limits onto RouterOS as a
    /ppp/profile, so provision_pppoe_user()'s `profile=` (also
    plan_to_profile_name(plan) - same rule as the hotspot side) always
    names something that actually exists. Same _plan_reconcile()/_write()
    machinery, same matched-by-name convention, same dry-run contract.

    No shared-users field here - that's a /ip/hotspot/user/profile concept
    (concurrent logins under one hotspot username); /ppp/profile has no
    equivalent, each PPPoE secret is inherently one connection.

    Field mapping, from plan.get_technical_config('pppoe'):
      rate-limit      = "{upload}{unit-suffix}/{download}{unit-suffix}"
                         (same rx-rate/tx-rate convention as the hotspot side)
      session-timeout = f"{session_timeout}s" (seconds, same as hotspot side)
    """
    changes: List[str] = []
    unchanged: List[str] = []
    failed: List[str] = []
    empty_details = {'changes': changes, 'unchanged': unchanged, 'failed': failed}

    api_pool = RouterOsApiPool(
        router.ip,
        username=router.username,
        password=router.password,
        port=router.port,
        plaintext_login=True,
    )
    try:
        api = api_pool.get_api()
    except Exception as e:
        return False, f"{type(e).__name__}: {e}", empty_details

    try:
        profile_name = plan_to_profile_name(plan)
        config = plan.get_technical_config('pppoe')

        rate_limit = "{}/{}".format(
            _routeros_rate_token(config['upload_speed'], config.get('upload_unit', 'Mbps')),
            _routeros_rate_token(config['download_speed'], config.get('download_unit', 'Mbps')),
        )
        session_timeout = f"{config.get('session_timeout') or 86400}s"

        ppp_profiles = api.get_resource('/ppp/profile').get() or []
        existing = next((p for p in ppp_profiles if p.get('name') == profile_name), None)
        _plan_reconcile(
            changes, unchanged, failed, dry_run, api, '/ppp/profile', existing,
            {
                'name': profile_name, 'rate-limit': rate_limit,
                'session-timeout': session_timeout,
            },
            profile_name,
        )

        overall_message = (
            f"{len(changes)} change(s) {'would be' if dry_run else 'were'} applied, "
            f"{len(unchanged)} item(s) already correct"
        )
        return True, overall_message, {'changes': changes, 'unchanged': unchanged, 'failed': failed}

    except Exception as e:
        logger.error(f"push_pppoe_profile failed for plan {getattr(plan, 'id', '?')} on {router.ip}: {e}")
        return False, f"push_pppoe_profile failed: {e}", {'changes': changes, 'unchanged': unchanged, 'failed': failed}
    finally:
        try:
            api_pool.disconnect()
        except Exception:
            pass


def remove_plan_profile(plan, router, dry_run: bool = False) -> Tuple[bool, str, Dict]:
    """
    Idempotent removal of the /ip/hotspot/user/profile matching
    plan_to_profile_name(plan) on `router` - the plan-delete counterpart
    to push_plan_profile(). A no-op (not an error, appended to
    'unchanged') if no such profile exists on this router; matched and
    removed by exact name only, never touches any other profile. Uses
    the same _write() primitive push_plan_profile()/_plan_reconcile()
    use, just with method='remove'.

    dry_run=True: read-only, reports what would be removed without
    removing it.
    """
    changes: List[str] = []
    unchanged: List[str] = []
    failed: List[str] = []
    empty_details = {'changes': changes, 'unchanged': unchanged, 'failed': failed}

    api_pool = RouterOsApiPool(
        router.ip,
        username=router.username,
        password=router.password,
        port=router.port,
        plaintext_login=True,
    )
    try:
        api = api_pool.get_api()
    except Exception as e:
        return False, f"{type(e).__name__}: {e}", empty_details

    try:
        profile_name = plan_to_profile_name(plan)
        path = '/ip/hotspot/user/profile'
        rows = api.get_resource(path).get() or []
        existing = next((p for p in rows if p.get('name') == profile_name), None)

        if existing is None:
            unchanged.append(f"{path} ({profile_name}): already absent, nothing to remove")
        elif dry_run:
            changes.append(f"REMOVE {path} id={existing.get('id')} name={profile_name}")
        else:
            try:
                _write(api, path, 'remove', {'id': existing['id']})
            except Exception as e:
                failed.append(f"REMOVE {path} id={existing.get('id')} name={profile_name} -> ERROR: {e}")
                raise
            changes.append(f"REMOVE {path} id={existing.get('id')} name={profile_name}")

        overall_message = (
            f"{len(changes)} change(s) {'would be' if dry_run else 'were'} applied, "
            f"{len(unchanged)} item(s) already correct"
        )
        return True, overall_message, {'changes': changes, 'unchanged': unchanged, 'failed': failed}

    except Exception as e:
        logger.error(f"remove_plan_profile failed for plan {getattr(plan, 'id', '?')} on {router.ip}: {e}")
        return False, f"remove_plan_profile failed: {e}", {'changes': changes, 'unchanged': unchanged, 'failed': failed}
    finally:
        try:
            api_pool.disconnect()
        except Exception:
            pass


class MikroTikConnectionManager:
    """
    Enhanced manager class for handling multiple MikroTik router connections with utility functions.
    """
    
    @staticmethod
    def test_router_connection(ip: str, username: str, password: str, port: int = None, timeout: int = None) -> Dict:
        """
        Static method to test router connection without creating instance.
        
        Returns:
            dict: Connection test results
        """
        connection_config = MikroTikConfig.get_connection_config()
        port = port or connection_config.get('PORT', 8728)
        timeout = timeout or connection_config.get('TIMEOUT', 10)
        
        connector = MikroTikConnector(ip, username, password, port, timeout)
        return connector.test_connection()
    
    @staticmethod
    def validate_router_credentials(ip: str, username: str, password: str, port: int = None) -> Dict:
        """
        Validate router credentials and return capabilities.
        
        Returns:
            dict: Validation results and router capabilities
        """
        if not ROUTEROS_AVAILABLE:
            return {
                'valid': False,
                'message': 'routeros-api package not installed',
                'capabilities': {}
            }
        
        connection_config = MikroTikConfig.get_connection_config()
        port = port or connection_config.get('PORT', 8728)
        
        connector = MikroTikConnector(ip, username, password, port)
        test_results = connector.test_connection()
        
        if not test_results.get('system_access'):
            return {
                'valid': False,
                'message': 'Invalid credentials or router not accessible',
                'capabilities': {},
                'error_messages': test_results.get('error_messages', [])
            }
        
        return {
            'valid': True,
            'message': 'Credentials validated successfully',
            'capabilities': test_results.get('capabilities', {}),
            'system_info': test_results.get('system_info', {}),
            'connection_info': {
                'response_time': test_results.get('response_time'),
                'basic_connectivity': test_results.get('basic_connectivity'),
                'api_connection': test_results.get('api_connection')
            }
        }
    
    @staticmethod
    def get_connection_templates() -> Dict:
        """
        Get predefined configuration templates for different use cases.
        
        Returns:
            dict: Configuration templates
        """
        hotspot_defaults = MikroTikConfig.get_hotspot_defaults()
        pppoe_defaults = MikroTikConfig.get_pppoe_defaults()
        
        return {
            'public_wifi': {
                'name': 'Public WiFi Hotspot',
                'description': 'Standard configuration for public WiFi access',
                'hotspot_config': {
                    'ssid': hotspot_defaults['default_ssid'],
                    'bandwidth_limit': '5M/5M',
                    'session_timeout': 120,
                    'max_users': 100,
                    'welcome_message': 'Welcome to our WiFi service',
                    'ip_pool': '192.168.100.10-192.168.100.200'
                },
                'recommended_for': ['cafes', 'restaurants', 'public spaces']
            },
            'enterprise_hotspot': {
                'name': 'Enterprise Hotspot',
                'description': 'Advanced configuration for enterprise environments',
                'hotspot_config': {
                    'ssid': f"{hotspot_defaults['default_ssid']}-Enterprise",
                    'bandwidth_limit': '20M/20M',
                    'session_timeout': 480,
                    'max_users': 50,
                    'welcome_message': 'Enterprise WiFi Access',
                    'ip_pool': '192.168.200.10-192.168.200.100'
                },
                'pppoe_config': {
                    'bandwidth_limit': '50M/50M',
                    'mtu': 1500,
                    'ip_pool_name': 'enterprise-pppoe-pool',
                    'ip_range': '192.168.201.10-192.168.201.100'
                },
                'recommended_for': ['offices', 'business centers', 'corporate environments']
            },
            'isp_pppoe': {
                'name': 'ISP PPPoE Service',
                'description': 'Configuration for ISP-style PPPoE services',
                'pppoe_config': {
                    'bandwidth_limit': '100M/50M',
                    'mtu': 1492,
                    'ip_pool_name': 'isp-pppoe-pool',
                    'ip_range': '192.168.1.10-192.168.1.254',
                    'service_name': 'ISP-PPPoE'
                },
                'recommended_for': ['internet service providers', 'wisp operations']
            },
            'basic_router': {
                'name': 'Basic Router Setup',
                'description': 'Minimal configuration for basic routing',
                'basic_config': {
                    'enable_api': True,
                    'enable_ssh': True,
                    'enable_www': True
                },
                'recommended_for': ['basic routing', 'network gateways']
            }
        }
    
    @staticmethod
    def get_supported_models() -> Dict:
        """
        Get information about supported MikroTik models and their capabilities.
        
        Returns:
            dict: Supported models information
        """
        return {
            'beginner_series': {
                'models': ['hAP lite', 'hAP ac', 'hAP ac²', 'hAP ax²'],
                'capabilities': ['hotspot', 'pppoe', 'basic_qos', 'wireless'],
                'max_users': 50,
                'description': 'Entry-level devices for small deployments'
            },
            'home_series': {
                'models': ['hEX', 'hEX S', 'hEX PoE'],
                'capabilities': ['hotspot', 'pppoe', 'advanced_qos', 'vlan'],
                'max_users': 100,
                'description': 'Home and small office routers'
            },
            'business_series': {
                'models': ['RB4011', 'RB5009', 'CCR1009'],
                'capabilities': ['hotspot', 'pppoe', 'advanced_qos', 'vlan', 'advanced_routing'],
                'max_users': 500,
                'description': 'Business-grade routers for larger deployments'
            },
            'service_provider': {
                'models': ['CCR2004', 'CCR2116', 'CCR2216'],
                'capabilities': ['hotspot', 'pppoe', 'advanced_qos', 'vlan', 'advanced_routing', 'high_performance'],
                'max_users': 1000,
                'description': 'Carrier-grade routers for service providers'
            }
        }
    
    @staticmethod
    def check_requirements() -> Dict:
        """
        Check system requirements and dependencies for MikroTik integration.
        
        Returns:
            dict: Requirements check results
        """
        return {
            'routeros_api_available': ROUTEROS_AVAILABLE,
            'django_available': DJANGO_AVAILABLE,
            'python_version': {
                'current': '.'.join(map(str, sys.version_info[:3])),
                'required': '3.7+',
                'compatible': sys.version_info >= (3, 7)
            },
            'dependencies': {
                'routeros-api': ROUTEROS_AVAILABLE,
                'django': DJANGO_AVAILABLE,
            },
            'recommendations': [
                'Install routeros-api: pip install routeros-api',
                'For Django integration: ensure Django is properly configured',
            ] if not ROUTEROS_AVAILABLE else []
        }
    
    @staticmethod
    def cleanup_all_connections():
        """Clean up all connection pools."""
        ConnectionPoolManager.disconnect_all_pools()


# Utility functions for common operations
def quick_connection_test(ip: str, username: str, password: str, port: int = None) -> Tuple[bool, str]:
    """
    Quick connection test for basic validation.
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        connection_config = MikroTikConfig.get_connection_config()
        port = port or connection_config.get('PORT', 8728)
        
        connector = MikroTikConnector(ip, username, password, port, timeout=5, max_retries=1)
        test_results = connector.test_connection()
        
        if test_results.get('system_access'):
            return True, "Connection successful"
        else:
            errors = test_results.get('error_messages', ['Unknown error'])
            return False, f"Connection failed: {errors[0]}"
            
    except Exception as e:
        return False, f"Connection test error: {str(e)}"


def validate_mikrotik_configuration(config: Dict) -> Tuple[bool, List[str]]:
    """
    Validate MikroTik configuration parameters.
    
    Returns:
        tuple: (is_valid: bool, error_messages: list)
    """
    errors = []
    
    required_fields = ['ip', 'username', 'password']
    for field in required_fields:
        if field not in config or not config[field]:
            errors.append(f"Missing required field: {field}")
    
    if 'ip' in config:
        ip_pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
        if not re.match(ip_pattern, config['ip']):
            errors.append("Invalid IP address format")
    
    if 'port' in config:
        try:
            port = int(config['port'])
            if not (1 <= port <= 65535):
                errors.append("Port must be between 1 and 65535")
        except (ValueError, TypeError):
            errors.append("Port must be a valid number")
    
    return len(errors) == 0, errors


def get_connector_version() -> Dict[str, str]:
    """
    Get the version information for the MikroTik connector.
    
    Returns:
        dict: Version information
    """
    return {
        'version': '2.1.0',
        'compatibility': 'MikroTik RouterOS 6.0+',
        'dependencies': {
            'routeros_api': '2.3.0+',
            'python': '3.7+',
            'django': '3.2+'
        },
        'features': [
            'Enhanced security with SSL/TLS support',
            'Connection pooling with monitoring',
            'Database integration with MySQL',
            'Environment-aware configuration',
            'Hotspot and PPPoE configuration',
            'Comprehensive error handling'
        ]
    }


# Export main classes and functions
__all__ = [
    'MikroTikConnector',
    'MikroTikConnectionManager',
    'ConnectionPoolManager',
    'SecurityConfig',
    'MikroTikConfig',
    'MonitoringManager',
    'DatabaseManager',
    'quick_connection_test',
    'validate_mikrotik_configuration',
    'get_connector_version'
]