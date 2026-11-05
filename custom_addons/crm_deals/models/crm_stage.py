
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class CrmStage(models.Model):
    _inherit = 'crm.stage'

    schedule_budget_review = fields.Boolean(
        string='Schedule Budget Review Meeting',
        help=(
            "A lead reaching this stage gets a Budget Review Meeting "
            "activity. Seeded once on Budget Proposal Ready; move it to "
            "another stage from here whenever the pipeline changes."
        ),
    )

    @api.model
    def _flag_budget_review_stage(self):
        """Flag only the dedicated GMS Budget Proposal Ready stage."""
        stage = self.env.ref(
            'crm_deals.stage_budget_proposal_ready',
            raise_if_not_found=False,
        )

        if not stage:
            return False

        solutions = self.env['crm.team']._gms_solutions_team()

        if not solutions or set(stage.team_ids.ids) != {solutions.id}:
            raise ValueError(
                "Budget Proposal Ready is not exclusively assigned "
                "to the GMS Solutions team. Review stage configuration."
            )

        if not stage.schedule_budget_review:
            stage.schedule_budget_review = True
            return True

        return False

    @api.model
    def _seed_gms_pipeline_stages(self):
        """Legacy entry point retained for migration compatibility.

        Dedicated GMS stages are initialized by crm.team.
        This method intentionally does not modify existing stages.
        """
        _logger.warning(
            "Legacy global CRM stage seeding skipped. "
            "Dedicated GMS stages are managed by crm.team."
        )
        return False
