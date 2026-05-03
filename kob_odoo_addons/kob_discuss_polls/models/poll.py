from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError


class KobPoll(models.Model):
    _name = "kob.poll"
    _description = "KOB Discuss Poll"
    _order = "create_date desc"

    question = fields.Char(required=True)
    creator_id = fields.Many2one(
        "res.users",
        default=lambda s: s.env.user,
        required=True,
        index=True,
    )
    channel_id = fields.Many2one("discuss.channel", required=True, index=True)
    expires_at = fields.Datetime()
    is_closed = fields.Boolean(compute="_compute_is_closed", store=False)
    option_ids = fields.One2many("kob.poll.option", "poll_id")
    vote_ids = fields.One2many("kob.poll.vote", "poll_id")
    total_votes = fields.Integer(compute="_compute_totals")

    @api.depends("expires_at")
    def _compute_is_closed(self):
        now = fields.Datetime.now()
        for p in self:
            p.is_closed = bool(p.expires_at and p.expires_at <= now)

    @api.depends("vote_ids")
    def _compute_totals(self):
        for p in self:
            p.total_votes = len(p.vote_ids)

    @api.model
    def create_from_command(self, channel_id, question, options, hours=24):
        """Create poll from /poll slash command."""
        channel = self.env["discuss.channel"].browse(channel_id)
        if not channel.exists():
            raise AccessError(_("Channel not found"))
        poll = self.create({
            "question": question,
            "channel_id": channel_id,
            "expires_at": fields.Datetime.now() + timedelta(hours=hours),
            "option_ids": [(0, 0, {"label": opt}) for opt in options],
        })
        # Post a message in the channel referencing the poll
        body = _(
            "<div class='kob_poll_anchor' data-poll-id='%(id)s'>"
            "📊 <b>%(q)s</b> — %(n)s options · expires in %(h)sh"
            "</div>"
        ) % {"id": poll.id, "q": question, "n": len(options), "h": hours}
        channel.message_post(body=body, message_type="comment")
        return poll.id

    def vote(self, option_id):
        """Cast vote — one vote per user per poll, switching allowed."""
        self.ensure_one()
        if self.is_closed:
            raise UserError(_("Poll is closed"))
        Vote = self.env["kob.poll.vote"]
        existing = Vote.search([
            ("poll_id", "=", self.id),
            ("user_id", "=", self.env.user.id),
        ], limit=1)
        if existing:
            existing.option_id = option_id
        else:
            Vote.create({
                "poll_id": self.id,
                "user_id": self.env.user.id,
                "option_id": option_id,
            })
        return self.read_results()

    def read_results(self):
        self.ensure_one()
        results = []
        total = len(self.vote_ids)
        for opt in self.option_ids:
            n = sum(1 for v in self.vote_ids if v.option_id.id == opt.id)
            results.append({
                "option_id": opt.id,
                "label": opt.label,
                "count": n,
                "pct": round(100.0 * n / total, 1) if total else 0,
            })
        return {
            "id": self.id,
            "question": self.question,
            "is_closed": self.is_closed,
            "total_votes": total,
            "results": results,
            "my_vote": self.env["kob.poll.vote"].search([
                ("poll_id", "=", self.id),
                ("user_id", "=", self.env.user.id),
            ]).option_id.id or False,
        }


class KobPollOption(models.Model):
    _name = "kob.poll.option"
    _description = "KOB Poll Option"
    _order = "sequence,id"

    poll_id = fields.Many2one("kob.poll", required=True, ondelete="cascade", index=True)
    label = fields.Char(required=True)
    sequence = fields.Integer(default=10)


class KobPollVote(models.Model):
    _name = "kob.poll.vote"
    _description = "KOB Poll Vote"

    poll_id = fields.Many2one("kob.poll", required=True, ondelete="cascade", index=True)
    user_id = fields.Many2one(
        "res.users",
        default=lambda s: s.env.user,
        required=True,
        index=True,
    )
    option_id = fields.Many2one("kob.poll.option", required=True, ondelete="cascade")

    _sql_constraints = [
        ("unique_user_per_poll", "unique(poll_id, user_id)",
         "User can only vote once per poll."),
    ]
