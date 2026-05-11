"""
Integrations package — platform-specific adapters for connecting external
ecommerce stores to SalesForge.

Each integration implements the `BaseIntegration` interface and is
registered in `sync_service.INTEGRATION_REGISTRY`. Adding a new platform
is a matter of writing one subclass + one line in the registry.
"""
