from . import models
from . import controllers
from . import wizard



def post_init_hook(env):
    """Initialize dedicated GMS CRM pipelines on a fresh installation."""
    env['crm.team']._seed_gms_sales_teams()
    env['crm.stage']._flag_budget_review_stage()
