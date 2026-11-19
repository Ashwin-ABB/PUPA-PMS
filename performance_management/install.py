from performance_management.kra.doctype.ho_traffic_light_settings.ho_traffic_light_settings import (
	ensure_defaults as ho_traffic_light_defaults,
)
from performance_management.kra.doctype.internal_feedback_settings.internal_feedback_settings import (
	ensure_defaults as internal_feedback_defaults,
)
from performance_management.kra.doctype.rating_score_master.rating_score_master import (
	ensure_defaults as rating_score_defaults,
)
from performance_management.sales_traffic_light.traffic_light import ensure_rule_sets as sales_rule_sets
from performance_management.worker_driver_security_tl.traffic_light import ensure_rule_sets as wds_rule_sets


def ensure_defaults():
	"""Seed every settings and master record. Runs after install and after each migrate."""
	internal_feedback_defaults()
	ho_traffic_light_defaults()
	rating_score_defaults()
	sales_rule_sets()
	wds_rule_sets()
