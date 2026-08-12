import csv
import json
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from odoo.api import Environment
    env: Environment


# ============================================================
# CONFIG
# ============================================================

DRY_RUN = True
# Change to False ONLY after reviewing the dry-run output.

MAPPING_CSV_PATH = "reparent_mapping.csv"

ICS_COMPANY_NAME = "INTEGRATED COMPUTER SERVICES INC."

# If True, the script will refuse to update records belonging
# to a different Odoo operating company.
ENFORCE_ICS_COMPANY = True


# ============================================================
# LOAD ODOO COMPANY
# ============================================================

ics_company = env["res.company"].sudo().search(
    [
        ("name", "=", ICS_COMPANY_NAME),
    ],
    limit=1,
)

if not ics_company:
    raise RuntimeError(
        f"Could not find Odoo company: {ICS_COMPANY_NAME!r}"
    )

print("=" * 80)
print("ICS CONTACT REPARENTING")
print("=" * 80)
print(f"Odoo Company: {ics_company.name} (id={ics_company.id})")
print(f"CSV: {MAPPING_CSV_PATH}")
print(f"DRY_RUN: {DRY_RUN}")
print(f"ENFORCE_ICS_COMPANY: {ENFORCE_ICS_COMPANY}")
print("=" * 80)


# ============================================================
# LOAD MAPPING CSV
# ============================================================

corrections = []

with open(
    MAPPING_CSV_PATH,
    newline="",
    encoding="utf-8-sig",
) as f:

    reader = csv.DictReader(f)

    required_columns = {
        "Database ID",
        "Name",
        "Company Database ID",
        "Company Name",
    }

    missing_columns = required_columns - set(reader.fieldnames or [])

    if missing_columns:
        raise RuntimeError(
            "Missing required CSV columns: "
            + ", ".join(sorted(missing_columns))
        )

    for row_number, row in enumerate(reader, start=2):

        try:
            contact_id = int(row["Database ID"])
            target_company_id = int(row["Company Database ID"])

        except (TypeError, ValueError):
            raise RuntimeError(
                f"Invalid Database ID on CSV row {row_number}: {row}"
            )

        corrections.append(
            {
                "row_number": row_number,
                "contact_id": contact_id,
                "contact_name": (row["Name"] or "").strip(),
                "target_company_id": target_company_id,
                "target_company_name": (
                    row["Company Name"] or ""
                ).strip(),
            }
        )


print(f"Loaded {len(corrections)} corrections.")
print("-" * 80)


# ============================================================
# PROCESS
# ============================================================

Partner = env["res.partner"].sudo()

audit_log = []
skipped = []
already_correct = []
updated = []


for c in corrections:

    contact = Partner.browse(c["contact_id"])
    target_parent = Partner.browse(c["target_company_id"])

    # --------------------------------------------------------
    # EXISTENCE CHECKS
    # --------------------------------------------------------

    if not contact.exists():

        skipped.append(
            {
                **c,
                "reason": "Contact record does not exist",
            }
        )

        print(
            f"SKIP contact id={c['contact_id']} "
            f"{c['contact_name']!r}: record does not exist"
        )

        continue


    if not target_parent.exists():

        skipped.append(
            {
                **c,
                "reason": "Target parent record does not exist",
            }
        )

        print(
            f"SKIP target id={c['target_company_id']} "
            f"for {c['contact_name']!r}: "
            "target record does not exist"
        )

        continue


    # --------------------------------------------------------
    # TARGET MUST BE A COMPANY PARTNER
    # --------------------------------------------------------

    if not target_parent.is_company:

        skipped.append(
            {
                **c,
                "reason": (
                    f"Target partner {target_parent.id} "
                    "is not marked as a company"
                ),
            }
        )

        print(
            f"SKIP {contact.name!r} (id={contact.id}): "
            f"target {target_parent.name!r} "
            f"(id={target_parent.id}) is not a company"
        )

        continue


    # --------------------------------------------------------
    # COMPANY-SCOPE SAFETY CHECKS
    # --------------------------------------------------------

    if ENFORCE_ICS_COMPANY:

        if (
            contact.company_id
            and contact.company_id != ics_company
        ):

            skipped.append(
                {
                    **c,
                    "reason": (
                        "Contact belongs to another Odoo company: "
                        f"{contact.company_id.name} "
                        f"(id={contact.company_id.id})"
                    ),
                }
            )

            print(
                f"SKIP {contact.name!r} (id={contact.id}): "
                f"contact company is "
                f"{contact.company_id.name!r} "
                f"(id={contact.company_id.id})"
            )

            continue


        if (
            target_parent.company_id
            and target_parent.company_id != ics_company
        ):

            skipped.append(
                {
                    **c,
                    "reason": (
                        "Target parent belongs to another Odoo company: "
                        f"{target_parent.company_id.name} "
                        f"(id={target_parent.company_id.id})"
                    ),
                }
            )

            print(
                f"SKIP {contact.name!r} (id={contact.id}): "
                f"target parent {target_parent.name!r} "
                f"belongs to "
                f"{target_parent.company_id.name!r}"
            )

            continue


    # --------------------------------------------------------
    # CURRENT STATE
    # --------------------------------------------------------

    before_parent_id = (
        contact.parent_id.id
        if contact.parent_id
        else None
    )

    before_parent_name = (
        contact.parent_id.name
        if contact.parent_id
        else None
    )


    # --------------------------------------------------------
    # ALREADY CORRECT
    # --------------------------------------------------------

    if before_parent_id == target_parent.id:

        entry = {
            **c,
            "actual_contact_name": contact.name,
            "actual_target_parent_name": target_parent.name,
            "before_parent_id": before_parent_id,
            "before_parent_name": before_parent_name,
            "after_parent_id": target_parent.id,
            "after_parent_name": target_parent.name,
            "status": "already_correct",
        }

        audit_log.append(entry)
        already_correct.append(entry)

        print(
            f"OK   {contact.name!r} (id={contact.id}) "
            f"already belongs to "
            f"{target_parent.name!r} "
            f"(id={target_parent.id})"
        )

        continue


    # --------------------------------------------------------
    # AUDIT ENTRY
    # --------------------------------------------------------

    entry = {
        **c,
        "actual_contact_name": contact.name,
        "actual_target_parent_name": target_parent.name,
        "contact_company_id": (
            contact.company_id.id
            if contact.company_id
            else None
        ),
        "contact_company_name": (
            contact.company_id.name
            if contact.company_id
            else None
        ),
        "target_company_scope_id": (
            target_parent.company_id.id
            if target_parent.company_id
            else None
        ),
        "target_company_scope_name": (
            target_parent.company_id.name
            if target_parent.company_id
            else None
        ),
        "before_parent_id": before_parent_id,
        "before_parent_name": before_parent_name,
        "after_parent_id": target_parent.id,
        "after_parent_name": target_parent.name,
        "status": (
            "planned"
            if DRY_RUN
            else "updated"
        ),
    }

    audit_log.append(entry)


    print(
        f"{'PLAN ' if DRY_RUN else 'WRITE'} "
        f"{contact.name!r} "
        f"(id={contact.id}): "
        f"{before_parent_name!r} "
        f"(id={before_parent_id}) "
        f"-> "
        f"{target_parent.name!r} "
        f"(id={target_parent.id})"
    )


    # --------------------------------------------------------
    # WRITE
    # --------------------------------------------------------

    if not DRY_RUN:

        contact.write(
            {
                "parent_id": target_parent.id,
            }
        )

        updated.append(entry)


# ============================================================
# SUMMARY
# ============================================================

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)

print(f"CSV rows:          {len(corrections)}")
print(f"Audited:           {len(audit_log)}")
print(f"Already correct:   {len(already_correct)}")
print(f"Skipped:           {len(skipped)}")

if DRY_RUN:
    planned_count = len(
        [
            x
            for x in audit_log
            if x["status"] == "planned"
        ]
    )

    print(f"Planned changes:   {planned_count}")
else:
    print(f"Updated:           {len(updated)}")


# ============================================================
# SKIPPED DETAILS
# ============================================================

if skipped:

    print()
    print("SKIPPED - NEEDS MANUAL REVIEW")
    print("-" * 80)

    for item in skipped:

        print(
            f"Row {item['row_number']}: "
            f"{item['contact_name']!r} "
            f"(id={item['contact_id']})"
        )

        print(
            f"  Target: "
            f"{item['target_company_name']!r} "
            f"(id={item['target_company_id']})"
        )

        print(
            f"  Reason: {item['reason']}"
        )


# ============================================================
# AUDIT FILE
# ============================================================

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

mode = (
    "dryrun"
    if DRY_RUN
    else "live"
)

log_filename = (
    f"reparent_audit_log_"
    f"{mode}_"
    f"{timestamp}.json"
)

with open(
    log_filename,
    "w",
    encoding="utf-8",
) as f:

    json.dump(
        {
            "timestamp": timestamp,
            "dry_run": DRY_RUN,
            "ics_company_id": ics_company.id,
            "ics_company_name": ics_company.name,
            "csv_path": MAPPING_CSV_PATH,
            "summary": {
                "csv_rows": len(corrections),
                "audited": len(audit_log),
                "already_correct": len(already_correct),
                "skipped": len(skipped),
                "updated": (
                    0
                    if DRY_RUN
                    else len(updated)
                ),
            },
            "changes": audit_log,
            "skipped": skipped,
        },
        f,
        indent=2,
        default=str,
    )


print()
print(f"Audit log written to: {log_filename}")

if DRY_RUN:

    print()
    print(
        "DRY RUN ONLY - NO RECORDS WERE CHANGED."
    )

    print(
        "Review every planned change and the "
        "SKIPPED section before setting "
        "DRY_RUN = False."
    )

else:

    print()
    print(
        f"LIVE RUN COMPLETE - "
        f"{len(updated)} contacts were updated."
    )