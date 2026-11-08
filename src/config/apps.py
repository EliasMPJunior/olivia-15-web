from django.contrib.admin.apps import AdminConfig

class OliviaAdminConfig(AdminConfig):
    default_site = 'config.admin.OliviaAdminSite'
