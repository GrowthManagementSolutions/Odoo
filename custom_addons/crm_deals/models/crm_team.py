import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

_SEEDED_PARAM = 'crm_deals.sales_teams_seeded'
_DEMO_USER_TEAMS_PARAM = 'crm_deals.demo_user_teams_seeded'

# Existing GMS teams are reused instead of renaming Odoo's
# default Sales Team, which belongs to ICS.
GMS_COMPANY_NAME = 'Growth Management Solutions, LLC'

GMS_SOLUTIONS_TEAM_NAME = 'GMS Sales - Solution Architect'
GMS_AGENT_TEAM_NAME = 'Channel Managers / Independent Agents'

SOLUTIONS_XMLID = 'crm_deals.team_gms_solutions'
AGENT_CHANNEL_XMLID = 'crm_deals.team_agent_channel'

# (xml id, name, sequence, fold, is_won, teams) per stage, where `teams` is
# 'shared' (team_ids empty - every pipeline), 'solutions' or 'agent'.
# Agent Channel's three stages are created when missing; everything else is
# already seeded by _seed_gms_pipeline_stages and only reconfigured here.
GMS_TEAM_STAGES = [
    ('stage_new_cold', 'New - Cold', 10, False, False, 'shared'),
    ('stage_new_warm', 'New - Warm', 20, False, False, 'shared'),
    ('stage_pricing_supplier_intro', 'Pricing & Supplier Intro', 22,
     False, False, 'agent'),
    ('stage_ia_selling', 'IA Selling', 24, False, False, 'agent'),
    ('stage_sold_reported', 'Sold – Reported', 26, False, False, 'agent'),
    ('stage_qualification_appointment_set', 'Qualification - Appointment Set',
     30, False, False, 'solutions'),
    ('stage_budget_proposal_needed', 'Budget Proposal Needed', 40,
     False, False, 'solutions'),
    ('stage_budget_proposal_ready', 'Budget Proposal Ready', 50,
     False, False, 'solutions'),
    ('stage_budget_proposal_reviewed_sent', 'Budget Proposal Reviewed/Sent',
     60, False, False, 'solutions'),
    ('stage_contract_sent_to_client', 'Contract Sent to Client', 70,
     False, False, 'solutions'),
    ('stage_verbal_commit', 'Verbal Commit', 80, False, False, 'solutions'),
    ('stage_contracts_requested_from_supplier',
     'Contracts Requested from Supplier', 90, False, False, 'solutions'),
    ('stage_closed_won', 'Closed - Won', 100, False, True, 'shared'),
    ('stage_closed_lost', 'Closed - Lost', 110, True, False, 'shared'),
    ('stage_cancelled', 'Cancelled', 120, True, False, 'solutions'),
]


class CrmTeam(models.Model):
    _inherit = 'crm.team'

    @api.model
    def _gms_company(self):
        """Locate the GMS company without using database-specific IDs."""
        company = self.env['res.company'].sudo().search([
            ('name', '=', GMS_COMPANY_NAME),
        ], limit=1)

        if not company:
            raise ValueError(
                'GMS company not found: %s' % GMS_COMPANY_NAME
            )

        return company

    @api.model
    def _gms_solutions_team(self):
        """Find the existing GMS Solutions team."""
        company = self._gms_company()

        return self.sudo().with_context(active_test=False).search([
            ('company_id', '=', company.id),
            ('name', '=', GMS_SOLUTIONS_TEAM_NAME),
        ], limit=1)

    @api.model
    def _gms_agent_channel_team(self):
        """Find the existing GMS Agent Channel team."""
        company = self._gms_company()

        return self.sudo().with_context(active_test=False).search([
            ('company_id', '=', company.id),
            ('name', '=', GMS_AGENT_TEAM_NAME),
        ], limit=1)

    @api.model
    def _seed_gms_sales_teams(self):
        """Set up GMS-specific stages without modifying existing stages."""
        params = self.env['ir.config_parameter'].sudo()
        if params.get_param(_SEEDED_PARAM):
            return False

        solutions = self._gms_solutions_team()
        agent = self._gms_agent_channel_team()

        if not solutions or not agent:
            raise ValueError(
                "GMS CRM setup requires both existing GMS sales teams. "
                "Solutions found: %s; Agent Channel found: %s"
                % (bool(solutions), bool(agent))
            )

        company = self._gms_company()
        if solutions.company_id != company or agent.company_id != company:
            raise ValueError("CRM teams must belong to GMS.")

        Data = self.env['ir.model.data'].sudo()
        Stage = self.env['crm.stage'].sudo().with_context(active_test=False)

        teams = {
            'shared': solutions | agent,
            'solutions': solutions,
            'agent': agent,
        }

        created = []

        for xmlid, name, sequence, fold, is_won, scope in GMS_TEAM_STAGES:
            full_xmlid = 'crm_deals.%s' % xmlid
            stage = self.env.ref(full_xmlid, raise_if_not_found=False)

            if stage:
                raise ValueError(
                    "Stage XML ID %s already exists. "
                    "Review its ownership before continuing." % full_xmlid
                )

            stage = Stage.create({
                'name': name,
                'sequence': sequence,
                'fold': fold,
                'is_won': is_won,
                'team_ids': [(6, 0, teams[scope].ids)],
            })

            Data.create({
                'module': 'crm_deals',
                'name': xmlid,
                'model': 'crm.stage',
                'res_id': stage.id,
                'noupdate': True,
            })

            created.append(name)

        params.set_param(_SEEDED_PARAM, 'True')

        _logger.info(
            "GMS CRM stages created for company %s: %s",
            company.name,
            ', '.join(created),
        )

        return True

    @api.model
    def _seed_demo_user_teams(self):
        """Put the two internal demo users (#63) on their sales team.

        This cannot live in `data/demo_users_data.xml`: Agent Channel is
        created by `_seed_gms_sales_teams()` in the `post_init_hook`, which
        runs *after* every data file, so `crm_deals.team_agent_channel` does
        not resolve while the data file is loading. Called from the
        `post_init_hook` right after the teams are seeded, and from
        `19.0.1.0.34` for a database that already has the module.

        Guarded by its own `ir.config_parameter`, like every other seeding
        step (key rule 44), so a membership removed afterwards in the UI is
        not silently put back by the next upgrade.
        """
        params = self.env['ir.config_parameter'].sudo()
        if params.get_param(_DEMO_USER_TEAMS_PARAM):
            return False

        added = []
        for user_xmlid, team in (
            ('crm_deals.user_demo_solution_architect', self._gms_solutions_team()),
            ('crm_deals.user_demo_channel_manager', self._gms_agent_channel_team()),
        ):
            user = self.env.ref(user_xmlid, raise_if_not_found=False)
            if not user or not team:
                continue
            if user.id not in team.member_ids.ids:
                team.member_ids = [(4, user.id)]
                added.append('%s -> %s' % (user.login, team.name))

        params.set_param(_DEMO_USER_TEAMS_PARAM, 'True')
        _logger.info('crm_deals #63: demo user team membership set. %s',
                     ', '.join(added) or 'nothing to add')
        return True
