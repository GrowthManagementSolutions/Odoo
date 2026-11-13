import binascii
import logging
import re

from odoo import _, http
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.tools import consteq, plaintext2html
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

_logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class CrmDealsPortal(CustomerPortal):
    """Referral-partner lead submission.

    Portal users have no access to crm.lead or crm.deal.line, and none is
    granted: every read and write here goes through sudo() and is always
    filtered to the current user's own submissions.
    """

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------
    def _has_partner_tag(self, tag_xmlid):
        tag = request.env.ref(tag_xmlid, raise_if_not_found=False)
        if not tag:
            return False
        return tag in request.env.user.partner_id.sudo().category_id

    def _is_referral_partner(self):
        """Referral Partner **or** Independent Agent may submit (#61).

        The name is kept because the templates and the home card read it; an
        independent agent sees exactly what a referral partner sees.
        """
        return (self._has_partner_tag(
                    'crm_deals.partner_category_referral_partner')
                or self._has_partner_tag(
                    'crm_deals.partner_category_independent_agent'))

    def _can_choose_agent(self):
        """Only a contact tagged both ways picks its own lead type (#61)."""
        return (self._has_partner_tag(
                    'crm_deals.partner_category_referral_partner')
                and self._has_partner_tag(
                    'crm_deals.partner_category_independent_agent'))

    def _default_partner_role(self):
        """A both-tagged contact's own default role (#62).

        Read from the contact, falling back to its commercial partner, and to
        Referral Partner when neither carries one.
        """
        partner = request.env.user.partner_id.sudo()
        role = (partner.default_partner_role
                or partner.commercial_partner_id.default_partner_role)
        return role or 'referral_partner'

    def _agent_checkbox_label(self):
        """The checkbox offers whichever role is *not* the default (#62)."""
        if self._default_partner_role() == 'independent_agent':
            return _("Hand this deal to GMS (Referral Partner)")
        return _("I'll work this deal myself (Independent Agent)")

    def _submitter_lead_type(self, post=None):
        """Lead type for this submitter, and the field that records them.

        A contact carrying both tags submits as its own Default Partner Role
        (#62, Referral Partner when unset), and the form's checkbox offers the
        other role.
        """
        is_referral = self._has_partner_tag(
            'crm_deals.partner_category_referral_partner')
        is_agent = self._has_partner_tag(
            'crm_deals.partner_category_independent_agent')
        ticked = bool((post or {}).get('as_independent_agent'))
        if is_referral and is_agent:
            default_role = self._default_partner_role()
            other = ('referral_partner' if default_role == 'independent_agent'
                     else 'independent_agent')
            role = other if ticked else default_role
        elif is_agent:
            role = 'independent_agent'
        else:
            role = 'referral_partner'
        party_field = ('independent_agent_id' if role == 'independent_agent'
                       else 'referral_partner_id')
        return role, party_field

    def _portal_new_warm_stage(self, team):
        """Return the configured New - Warm stage for the GMS team.

        Never adopt or create CRM stages from a portal request.
        """
        Team = request.env['crm.team'].sudo()
        gms_company = Team._gms_company()

        if not team or team.company_id != gms_company:
            raise UserError(_(
                "The GMS sales team is not configured correctly. "
                "Please contact your administrator."
            ))

        stage = request.env.ref(
            'crm_deals.stage_new_warm',
            raise_if_not_found=False
        )

        if (
            not stage
            or stage._name != 'crm.stage'
            or not stage.exists()
            or stage.is_won
            or (stage.team_ids and team not in stage.team_ids)
        ):
            raise UserError(_(
                "The GMS New - Warm stage is missing or incorrectly "
                "configured. Please contact your administrator."
            ))

        return stage

    def _lead_domain(self):
        """Show only this user's GMS referral submissions."""
        gms_company = request.env['crm.team'].sudo()._gms_company()

        return [
            ('company_id', '=', gms_company.id),
            ('portal_submitter_id', '=', request.env.user.partner_id.id),
        ]

    def _get_own_lead(self, lead_id):
        """Own submitted lead, or None. active_test=False so lost leads show."""
        lead = request.env['crm.lead'].sudo().with_context(
            active_test=False).search(self._lead_domain() + [('id', '=', lead_id)], limit=1)
        return lead or None

    # ------------------------------------------------------------------
    # Portal home tile
    # ------------------------------------------------------------------
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        # home() calls this with an empty counters list, so this flag (not a
        # *_count key, which would land in the portal_counters cache) is what
        # decides whether the card is rendered at all.
        values['is_referral_partner'] = self._is_referral_partner()
        if 'lead_count' in counters:
            values['lead_count'] = request.env['crm.lead'].sudo().with_context(
                active_test=False).search_count(self._lead_domain()) \
                if values['is_referral_partner'] else 0
        return values

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------
    @http.route(['/my/leads', '/my/leads/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_my_leads(self, page=1, sortby='date', **kw):
        if not self._is_referral_partner():
            return request.redirect('/my')
        Lead = request.env['crm.lead'].sudo().with_context(active_test=False)
        searchbar_sortings = {
            'date': {'label': _('Newest'), 'order': 'create_date desc'},
            'name': {'label': _('Company Name'), 'order': 'partner_name'},
            'contact': {'label': _('Contact Name'), 'order': 'contact_name'},
        }
        order = searchbar_sortings.get(sortby, searchbar_sortings['date'])['order']
        domain = self._lead_domain()
        total = Lead.search_count(domain)
        pager = portal_pager(
            url='/my/leads', url_args={'sortby': sortby},
            total=total, page=page, step=self._items_per_page,
        )
        leads = Lead.search(domain, order=order,
                            limit=self._items_per_page, offset=pager['offset'])
        request.session['my_leads_history'] = leads.ids[:100]
        return request.render('crm_deals.portal_my_leads', {
            'leads': leads,
            'page_name': 'lead',
            'pager': pager,
            'default_url': '/my/leads',
            'sortby': sortby,
            'searchbar_sortings': searchbar_sortings,
        })

    # ------------------------------------------------------------------
    # Detail
    # ------------------------------------------------------------------
    def _portal_visible_deal_lines(self, lead):
        """The deal lines a portal user may see: Accepted and Rejected only.

        Lines are grouped into blocks headed by a section. A block survives
        only if it still holds at least one Accepted or Rejected line, so a
        section whose lines are all Draft is dropped along with them. Notes
        travel with their block. Lines above the first section form a leading
        block with no heading.
        """
        lines = lead.deal_line_ids.sorted(lambda l: (l.sequence, l.id))
        blocks = [(None, [])]
        for line in lines:
            if line.display_type == 'line_section':
                blocks.append((line, []))
            else:
                blocks[-1][1].append(line)

        ordered_ids = []
        for section, members in blocks:
            kept = [line for line in members
                    if line.display_type
                    or line.status in ('accepted', 'rejected')]
            if not any(not line.display_type for line in kept):
                continue
            if section:
                ordered_ids.append(section.id)
            ordered_ids.extend(line.id for line in kept)
        return lines.browse(ordered_ids)

    @http.route(['/my/leads/<int:lead_id>'], type='http', auth='user', website=True)
    def portal_my_lead(self, lead_id, message=False, **kw):
        if not self._is_referral_partner():
            return request.redirect('/my')
        lead = self._get_own_lead(lead_id)
        if not lead:
            return request.not_found()
        # Only Accepted/Rejected lines, filtered here on the sudo'd recordset
        # so Draft lines never reach the template. Already sudo'd via the lead.
        deal_lines = self._portal_visible_deal_lines(lead)
        real_lines = deal_lines.filtered(lambda l: not l.display_type)
        return request.render('crm_deals.portal_my_lead', {
            'lead': lead,
            'deal_lines': deal_lines,
            'monthly_total': sum(real_lines.mapped('estimated_monthly_cost')),
            'onetime_total': sum(real_lines.mapped('estimated_one_time_revenue')),
            # sudo'd currency for the totals row; lines carry their own.
            'currency': real_lines[:1].currency_id or lead.company_currency,
            'page_name': 'lead',
            'message': message,
        })
    # ------------------------------------------------------------------
    # Submission form
    # ------------------------------------------------------------------
    def _lead_form_values(self):
        env = request.env
        return {
            'countries': env['res.country'].sudo().search([]),
            'states': env['res.country.state'].sudo().search([]),
            'industries': env['res.partner.industry'].sudo().search([]),
            'subsectors': env['res.partner.subsector'].sudo().search([]),
        }

    @http.route(['/my/leads/new'], type='http', auth='user', website=True,
                methods=['GET'])
    def portal_my_lead_new(self, **kw):
        if not self._is_referral_partner():
            return request.redirect('/my')
        values = self._lead_form_values()
        values.update({'page_name': 'lead', 'error': {}, 'lead_data': {},
                       'can_choose_agent': self._can_choose_agent(),
                       'agent_checkbox_label': self._agent_checkbox_label()})
        return request.render('crm_deals.portal_lead_form', values)

    @http.route(['/my/leads/new'], type='http', auth='user', website=True,
                methods=['POST'])
    def portal_my_lead_submit(self, **post):
        if not self._is_referral_partner():
            return request.redirect('/my')
        error = {}
        if not (post.get('partner_name') or '').strip():
            error['partner_name'] = _("Company Name is required.")
        if not (post.get('contact_name') or '').strip():
            error['contact_name'] = _("Contact Name is required.")
        email = (post.get('email_from') or '').strip()
        if not email:
            error['email_from'] = _("Email is required.")
        elif not EMAIL_RE.match(email):
            error['email_from'] = _("Please enter a valid email address.")
        if error:
            values = self._lead_form_values()
            values.update({'page_name': 'lead', 'error': error,
                           'lead_data': post,
                           'can_choose_agent': self._can_choose_agent(),
                           'agent_checkbox_label': self._agent_checkbox_label()})
            return request.render('crm_deals.portal_lead_form', values)

        partner = request.env.user.partner_id
        company_name = post['partner_name'].strip()
        use_leads = request.env.user.has_group('crm.group_use_lead')

        # Portal submissions belong exclusively to GMS.
        Team = request.env['crm.team'].sudo()
        gms_company = Team._gms_company()

        lead_type, party_field = self._submitter_lead_type(post)

        if lead_type == 'independent_agent':
            team = Team._gms_agent_channel_team()
        else:
            team = Team._gms_solutions_team()

        if not team or not team.active:
            raise UserError(_(
                "The required GMS sales team is unavailable. "
                "Please contact your administrator."
            ))

        vals = {
            'name': '%s - %s' % (company_name, _("Referral")),
            'company_id': gms_company.id,
            'team_id': team.id,
            'type': 'lead' if use_leads else 'opportunity',
            'partner_name': company_name,
            'contact_name': post['contact_name'].strip(),
            'email_from': email,
            'function': post.get('function') or False,
            'phone': post.get('phone') or False,
            'website': post.get('website') or False,
            'street': post.get('street') or False,
            'street2': post.get('street2') or False,
            'city': post.get('city') or False,
            'zip': post.get('zip') or False,
            'state_id': int(post['state_id']) if post.get('state_id') else False,
            'country_id': int(post['country_id']) if post.get('country_id') else False,
            'industry_id': int(post['industry_id']) if post.get('industry_id') else False,
            'subsector_id': int(post['subsector_id']) if post.get('subsector_id') else False,
            'description': plaintext2html(post['description'])
                           if (post.get('description') or '').strip() else False,
            'portal_submitter_id': partner.id,
        }
        vals['lead_type'] = lead_type
        vals[party_field] = partner.id
        vals['stage_id'] = self._portal_new_warm_stage(team).id
        # The default SA / CM and the salesperson are set in the create vals,
        # so the lead's own _default_* methods and _check_partner_type_write
        # never see a portal user (#61).
        missing = None
        if lead_type == 'referral_partner':
            architect = partner._get_default_budget_contact(
                'default_solution_architect_id')
            if architect:
                vals['solution_architect_ids'] = [(6, 0, architect.ids)]
                vals['user_id'] = self._portal_internal_user(architect)
            else:
                missing = _("Solution Architect")
        else:
            manager = partner._get_default_budget_contact(
                'default_channel_manager_id')
            if manager:
                vals['channel_manager_id'] = manager.id
                vals['user_id'] = self._portal_internal_user(manager)
            else:
                missing = _("Channel Manager")
        # Never the portal user. sudo() keeps env.user, so crm's own
        # `user_id` default would hand the lead to the submitter; the field is
        # therefore always set explicitly - the resolved internal user, else
        # the sales team's leader, else nobody.
        if not vals.get('user_id'):
            vals['user_id'] = self._portal_fallback_user(team)
        lead = request.env['crm.lead'].sudo().create(vals)
        self._portal_after_submit(lead, partner, lead_type, missing)
        return request.redirect('/my/leads/%s?message=submitted' % lead.id)

    def _portal_fallback_user(self, team):
        """Use only the selected GMS team's eligible leader."""
        gms_company = request.env['crm.team'].sudo()._gms_company()

        if not team or team.company_id != gms_company:
            return False

        user = team.user_id

        if (
            not user
            or not user.active
            or not user._is_internal()
            or gms_company not in user.company_ids
        ):
            return False

        return user.id

    def _portal_internal_user(self, contact):
        """Return an active internal user authorized for GMS, or False."""
        if not contact:
            return False

        gms_company = request.env['crm.team'].sudo()._gms_company()

        users = contact.sudo().user_ids.filtered(
            lambda user: (
                user.active
                and user._is_internal()
                and gms_company in user.company_ids
            )
        )

        return users[0].id if users else False


    def _portal_after_submit(self, lead, partner, lead_type, missing):
        """Confirmation mail, internal notice and followers (#61)."""
        lead = lead.sudo()
        type_label = dict(
            lead._fields['lead_type'].selection).get(lead_type, lead_type)
        if missing:
            lead.message_post(body=_(
                "No default %(role)s is set for %(partner)s; please assign "
                "one.", role=missing, partner=partner.display_name))
        lead.message_post(body=_(
            "New lead submitted via the portal by %(partner)s (%(type)s)",
            partner=partner.display_name, type=type_label))
        # Subscribe the people who should hear about it.
        followers = set()
        if lead.user_id:
            followers.add(lead.user_id.partner_id.id)
        for contact in (lead.solution_architect_ids | lead.channel_manager_id):
            followers.add(contact.id)
        leader = lead.team_id.user_id
        if leader:
            followers.add(leader.partner_id.id)
        followers.discard(False)
        if followers:
            lead.message_subscribe(partner_ids=list(followers))
        template = request.env.ref(
            'crm_deals.mail_template_portal_lead_submitted',
            raise_if_not_found=False)
        if template:
            template.sudo().send_mail(lead.id, force_send=False)
        self._portal_follow_up_activity(lead, partner, lead_type)
        return True

    def _portal_follow_up_activity(self, lead, partner, lead_type):
        """One Follow Up on New Lead activity per submission (#62).

        The default SA (referral) or CM (agent) gets it, else the lead's
        salesperson. Nobody at all means no activity and a chatter note: the
        activity going overdue after two days is the reassignment signal, so
        there is no cron and no timer.
        """
        # sudo throughout: a portal user cannot read mail.activity.type.
        activity_type = request.env.ref(
            'crm_deals.mail_activity_type_follow_up_new_lead',
            raise_if_not_found=False)
        if not activity_type:
            return False
        activity_type = activity_type.sudo()
        lead = lead.sudo()
        field = ('default_channel_manager_id'
                 if lead_type == 'independent_agent'
                 else 'default_solution_architect_id')
        contact = partner._get_default_budget_contact(field)
        user_id = self._portal_internal_user(contact) if contact else False
        if not user_id:
            user_id = lead.user_id.id
        if not user_id:
            role = (_("Channel Manager") if lead_type == 'independent_agent'
                    else _("Solution Architect"))
            lead.message_post(body=_(
                "No one to follow up this lead: set a default %(role)s on "
                "%(partner)s.", role=role, partner=partner.display_name))
            return False
        details = [
            _("Company: %s", lead.partner_name or ''),
            _("Contact: %s", lead.contact_name or ''),
        ]
        if lead.phone:
            details.append(_("Phone: %s", lead.phone))
        if lead.email_from:
            details.append(_("Email: %s", lead.email_from))
        note = '<p>%s</p>' % '<br/>'.join(details)
        if lead.description:
            note += '<p>%s</p>' % lead.description
        lead.sudo().activity_schedule(
            act_type_xmlid='crm_deals.mail_activity_type_follow_up_new_lead',
            date_deadline=activity_type._get_date_deadline(),
            summary=_("Follow up on new lead from %s", partner.display_name),
            note=note,
            user_id=user_id,
        )
        return True


# Tokens of budgets this visitor has already been allowed to open. The
# signature form posts no token, so this is what the sign call falls back to.
BUDGET_TOKEN_SESSION_KEY = 'crm_deals_budget_tokens'


class CrmDealsBudgetPortal(CustomerPortal):
    """Customer-facing Budget Summary (#58).

    Access is by access token, exactly like a sent quotation: the customer
    needs no portal account. Every read and write goes through sudo() after
    the token has been validated and is scoped to that one lead - key rule 2
    still holds, no ACL or record rule is granted on crm.lead or the deal
    line model. This is separate from the referral-partner /my/leads pages.
    """

    def _budget_token(self, lead_id, access_token=None):
        """The access token for this call, from wherever it reached us.

        `portal.signature_form` posts only `name` and `signature`, and a
        jsonrpc route never sees the `call_url` query string as a parameter -
        which is what made signing fail with "Invalid budget.". The token is
        therefore looked for in the JSON body, then in the query string (as
        sale's own `portal_quote_accept` does), then in the session, where
        the page put it the last time it was opened successfully.
        """
        if access_token:
            return access_token
        args_token = request.httprequest.args.get('access_token')
        if args_token:
            return args_token
        return (request.session.get(BUDGET_TOKEN_SESSION_KEY) or {}).get(
            str(lead_id))


    def _budget_remember_token(self, lead, access_token=None):
        """Remember only a token that was actually presented and validated."""
        if not access_token or not lead.access_token:
            return

        if not consteq(lead.access_token, access_token):
            return

        tokens = dict(request.session.get(BUDGET_TOKEN_SESSION_KEY) or {})
        if tokens.get(str(lead.id)) != access_token:
            tokens[str(lead.id)] = access_token
            request.session[BUDGET_TOKEN_SESSION_KEY] = tokens
    def _budget_lead(self, lead_id, access_token=None):
        """Return a GMS budget only when the visitor has view access."""
        lead = request.env['crm.lead'].sudo().browse(lead_id).exists()

        if not lead:
            _logger.info("Budget Summary: lead %s does not exist", lead_id)
            raise MissingError(_("This budget no longer exists."))

        # Never expose ICS opportunities through the GMS budget portal.
        gms_company = request.env['crm.team'].sudo()._gms_company()

        if lead.company_id != gms_company:
            _logger.warning(
                "Budget Summary: denied non-GMS lead %s",
                lead_id,
            )
            raise AccessError(_("This budget is not available."))

        # A valid access token allows viewing this specific budget.
        token = self._budget_token(lead_id, access_token)

        if token and lead.access_token and consteq(lead.access_token, token):
            return lead

        user = request.env.user

        if not user._is_public():
            partner = user.partner_id
            customer = lead.partner_id

            # Logged-in customers may view sent budgets belonging
            # to their commercial customer account.
            if (
                not user._is_internal()
                and customer
                and partner
                and lead.budget_sent_date
                and customer.commercial_partner_id
                == partner.commercial_partner_id
            ):
                return lead

            # Internal users may preview only records they can read
            # using their existing CRM permissions.
            if user._is_internal():
                try:
                    request.env['crm.lead'].browse(
                        lead_id
                    ).check_access('read')
                    return lead
                except AccessError:
                    pass

        _logger.info(
            "Budget Summary: refused access to lead %s "
            "for user %s (%s); token %s",
            lead_id,
            user.id,
            user.login,
            "mismatched" if token else "missing",
        )

        raise AccessError(_(
            "This budget link has expired or belongs to another customer. "
            "Ask your representative to send it again."
        ))


    def _budget_values(self, lead, access_token=None):
        """Prepare budget values without exposing an unpresented token."""
        values = lead._budget_data()

        # Only pass through a token that was actually supplied
        # and validated. Never reveal the stored token automatically.
        token = False

        if (
            access_token
            and lead.access_token
            and consteq(lead.access_token, access_token)
        ):
            token = access_token

        values.update({
            'lead': lead,
            'access_token': token or '',
            'page_name': 'budget_summary',
            'is_internal_user': request.env.user._is_internal(),
            'report_url': (
                '/my/budget/%s?report_type=pdf&download=true' % lead.id
            ),
            'backend_url': '/odoo/crm/%s' % lead.id,
        })
        return values

    def _budget_authorize_customer_action(self, lead, access_token=None):
        """Authorize customer budget decisions and signatures.

        View permission alone must not grant approval permission.
        The lead must already have passed the GMS company check.
        """
        gms_company = request.env['crm.team'].sudo()._gms_company()

        if lead.company_id != gms_company:
            raise AccessError(_("This budget is not available."))

        # Customers cannot approve or sign a budget before it is sent.
        if not lead.budget_sent_date:
            raise AccessError(_(
                "This Budget Summary has not been sent to the customer yet."
            ))

        user = request.env.user

        # Internal CRM users may preview budgets but cannot make
        # customer decisions or sign on the customer's behalf.
        if user._is_internal():
            raise AccessError(_(
                "Only the customer may approve or sign this budget."
            ))

        # A valid budget token authorizes the customer action.
        token = self._budget_token(lead.id, access_token)

        if (
            token
            and lead.access_token
            and consteq(lead.access_token, token)
        ):
            return True

        # A logged-in customer may act on a sent budget belonging
        # to their commercial customer account.
        if not user._is_public():
            partner = user.partner_id
            customer = lead.partner_id

            if (
                partner
                and customer
                and lead.budget_sent_date
                and customer.commercial_partner_id
                == partner.commercial_partner_id
            ):
                return True

        raise AccessError(_(
            "You are not authorized to approve or sign this budget."
        ))

    def _budget_content(self, lead, access_token=None):
        """The document card rendered on its own, so a decision can swap it
        in place instead of reloading the page."""
        return request.env['ir.qweb'].sudo()._render(
            'crm_deals.budget_summary_portal_content',
            self._budget_values(lead, access_token))

    # ------------------------------------------------------------------
    # Portal home and list
    # ------------------------------------------------------------------

    def _budget_customer_domain(self):
        """Return only sent GMS budgets belonging to this customer."""
        commercial = request.env.user.partner_id.commercial_partner_id
        gms_company = request.env['crm.team'].sudo()._gms_company()

        return [
            ('company_id', '=', gms_company.id),
            ('partner_id.commercial_partner_id', '=', commercial.id),
            ('budget_sent_date', '!=', False),
        ]

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if not request.env.user._is_public():
            values['budget_count'] = request.env['crm.lead'].sudo().search_count(
                self._budget_customer_domain())
        return values

    @http.route(['/my/budgets'], type='http', auth='user', website=True)
    def portal_my_budgets(self, **kw):
        budgets = request.env['crm.lead'].sudo().search(
            self._budget_customer_domain(), order='budget_sent_date desc')
        return request.render('crm_deals.portal_my_budgets', {
            'budgets': budgets,
            'page_name': 'budget_summary',
            'default_url': '/my/budgets',
        })

    @http.route(['/my/budget/<int:lead_id>'], type='http', auth='public',
                website=True)
    def portal_budget_summary(self, lead_id, access_token=None,
                              report_type=None, download=False, **kw):
        try:
            lead = self._budget_lead(lead_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        # The signature form posts no token, so remember the one this page
        # was opened with - or the lead's own, when the visitor got in as the
        # customer without a link.
        token = self._budget_token(lead_id, access_token)
        self._budget_remember_token(lead, token)
        if report_type in ('pdf', 'html', 'text'):
            return self._show_report(
                model=lead, report_type=report_type,
                report_ref='crm_deals.action_report_budget_summary',
                download=download)
        values = self._budget_values(lead, token)
        # Portal chatter on the lead, so the customer can message the
        # representative; messages land in the lead's own chatter.
        values.update(self._get_page_view_values(
            lead, values['access_token'], values, '_budget_history', False))
        return request.render('crm_deals.budget_summary_portal', values)

    @http.route(['/my/budget/<int:lead_id>/line/<int:line_id>/<string:decision>'],
                type='jsonrpc', auth='public', website=True)
    def portal_budget_decision(self, lead_id, line_id, decision,
                               access_token=None, **kw):
        """Accept or reject one service, instantly."""
        try:
            lead = self._budget_lead(lead_id, access_token)
            self._budget_authorize_customer_action(
                lead, access_token
            )
        except (AccessError, MissingError) as error:
            return {'error': error.args[0] if error.args else str(error)}
        if lead.budget_signed_on:
            return {'error': _("This budget has been signed and can no longer "
                               "be changed.")}
        if decision not in ('accept', 'reject'):
            return {'error': _("Unknown decision.")}
        line = lead.deal_line_ids.filtered(
            lambda l: l.id == line_id and not l.display_type)
        if not line:
            _logger.info("Budget Summary: line %s is not on lead %s",
                         line_id, lead_id)
            return {'error': _("This service is no longer on the budget. "
                               "Refresh the page and try again.")}
        status = 'accepted' if decision == 'accept' else 'rejected'
        try:
            line.action_portal_decision(status)
        except UserError as error:
            return {'error': error.args[0] if error.args else str(error)}
        self._budget_remember_token(lead, self._budget_token(lead_id, access_token))
        data = lead._budget_data()
        return {
            'line_id': line.id,
            'status': status,
            # The whole document card, re-rendered: badges, buttons,
            # subtotals and totals all move together.
            'content': self._budget_content(lead, access_token),
            'values': lead._budget_live_values(),
            'all_decided': data['all_decided'],
        }

    @http.route(['/my/budget/<int:lead_id>/sign'], type='jsonrpc',
                auth='public', website=True)
    def portal_budget_sign(self, lead_id, access_token=None, name=None,
                           signature=None, **kw):
        try:
            lead = self._budget_lead(lead_id, access_token)
            self._budget_authorize_customer_action(
                lead, access_token
            )
        except (AccessError, MissingError) as error:
            return {'error': error.args[0] if error.args else str(error)}
        if lead.budget_signed_on:
            return {'error': _("This budget has already been signed.")}
        if request.env.user._is_internal():
            return {'error': _("Signing is the customer's action.")}
        if not signature:
            return {'error': _("Signature is missing.")}
        if not lead._budget_data()['all_decided']:
            return {'error': _("Please accept or reject every service before "
                               "signing.")}
        _logger.info("Budget Summary: lead %s signed by %s", lead_id, name)
        try:
            lead._budget_apply_signature(name, signature)
        except (TypeError, binascii.Error):
            return {'error': _("Invalid signature data.")}
        return {'force_refresh': True, 'redirect_url': '/my/budget/%s' % lead.id}
