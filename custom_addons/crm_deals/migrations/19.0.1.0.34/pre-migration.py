import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Demo-user adoption disabled for the GMS deployment."""
    _logger.info(
        "Skipping legacy CRM Deals demo-user adoption."
    )