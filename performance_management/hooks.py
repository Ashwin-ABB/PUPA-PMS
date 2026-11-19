app_name = "performance_management"
app_title = "Performance Management"
app_publisher = "Pupa"
app_description = "KRA, KPI, PTS, ratings and traffic light scoring for staff performance"
app_email = "admin@example.com"
app_license = "mit"
required_apps = ["frappe", "hrms"]

after_install = "performance_management.install.ensure_defaults"
after_migrate = ["performance_management.install.ensure_defaults"]

# makes get_print_data() available to the coloured Sales Traffic Light print formats
jinja = {"methods": ["performance_management.sales_traffic_light.traffic_light.get_print_data"]}
