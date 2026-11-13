import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Demo-user team assignment disabled for the GMS deployment."""
    _logger.info(
        "Skipping legacy CRM Deals demo-user team assignment."
    )