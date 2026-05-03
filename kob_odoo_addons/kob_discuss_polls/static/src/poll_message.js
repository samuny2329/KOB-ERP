/** @odoo-module **/

// Slash command /poll → register & handle in Discuss composer.
// Also patches Message rendering to show inline poll widget when message body
// contains <div class="kob_poll_anchor" data-poll-id="N">.

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { browser } from "@web/core/browser/browser";

export class KobPollWidget extends Component {
    static template = "kob_discuss_polls.PollWidget";
    static props = {
        pollId: { type: Number },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            poll: null,
        });
        onWillStart(() => this.refresh());
    }

    async refresh() {
        try {
            const data = await this.orm.call("kob.poll", "read_results", [[this.props.pollId]]);
            this.state.poll = data;
        } catch (e) {
            console.warn("[KobPoll] refresh failed", e);
        } finally {
            this.state.loading = false;
        }
    }

    async onVote(optionId) {
        try {
            const data = await this.orm.call("kob.poll", "vote", [[this.props.pollId], optionId]);
            this.state.poll = data;
            this.notification.add("Vote recorded", { type: "success" });
        } catch (e) {
            this.notification.add("Vote failed: " + (e.message || e), { type: "danger" });
        }
    }
}

// Auto-mount poll widgets where anchor divs exist
function mountPollAnchors() {
    document.querySelectorAll(".kob_poll_anchor:not(.kob_poll_mounted)").forEach((el) => {
        const pollId = parseInt(el.dataset.pollId, 10);
        if (!pollId) return;
        el.classList.add("kob_poll_mounted");
        // Render via simple HTML — full OWL mount in Discuss would need patching
        // mail.message component; we keep it lightweight with vanilla JS.
        renderInline(el, pollId);
    });
}

async function renderInline(anchor, pollId) {
    const orm = window.odoo?.__DEBUG__?.services?.orm
        || (window.__owl_app__ && window.__owl_app__.env.services.orm);
    if (!orm) return;
    try {
        const data = await orm.call("kob.poll", "read_results", [[pollId]]);
        const html = `
            <div class="kob_poll_inline">
                <div class="kob_poll_q"><b>📊 ${escapeHtml(data.question)}</b></div>
                ${data.results.map(r => `
                    <button class="kob_poll_opt ${data.my_vote === r.option_id ? 'kob_my_vote' : ''}"
                            data-option-id="${r.option_id}"
                            ${data.is_closed ? 'disabled' : ''}>
                        <span>${escapeHtml(r.label)}</span>
                        <span class="kob_poll_count">${r.count} (${r.pct}%)</span>
                        <div class="kob_poll_bar" style="width:${r.pct}%"></div>
                    </button>
                `).join("")}
                <div class="kob_poll_meta">${data.total_votes} votes${data.is_closed ? ' · CLOSED' : ''}</div>
            </div>
        `;
        anchor.innerHTML = html;
        anchor.querySelectorAll(".kob_poll_opt").forEach(btn => {
            btn.addEventListener("click", async () => {
                const oid = parseInt(btn.dataset.optionId, 10);
                try {
                    await orm.call("kob.poll", "vote", [[pollId], oid]);
                    renderInline(anchor, pollId);
                } catch (e) {
                    console.warn("Vote failed", e);
                }
            });
        });
    } catch (e) {
        anchor.textContent = "[Poll unavailable]";
    }
}

function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
}

// Watch for new messages in Discuss
const obs = new MutationObserver(() => mountPollAnchors());
function bootstrap() {
    if (!document.body) {
        browser.setTimeout(bootstrap, 100);
        return;
    }
    obs.observe(document.body, { childList: true, subtree: true });
    mountPollAnchors();
}
bootstrap();

// Slash-command service: detect /poll in composer textarea on submit
const slashCommandService = {
    dependencies: ["orm", "notification"],
    start(env, { orm, notification }) {
        document.addEventListener("keydown", async (ev) => {
            if (ev.key !== "Enter" || ev.shiftKey) return;
            const ta = ev.target.closest("textarea.o-mail-Composer-input, .o-mail-Composer-input");
            if (!ta) return;
            const text = (ta.value || ta.innerText || "").trim();
            if (!text.startsWith("/poll ")) return;
            // Format: /poll Question? opt1, opt2, opt3
            const body = text.slice(6).trim();
            const qMatch = body.match(/^(.+?)\?\s*(.*)$/);
            if (!qMatch) return;
            const question = qMatch[1].trim() + "?";
            const options = qMatch[2].split(",").map(o => o.trim()).filter(Boolean);
            if (options.length < 2) return;
            // Find current channel
            const channelEl = document.querySelector(".o-mail-DiscussSidebarChannel-active, [data-channel-id]");
            const channelId = channelEl ? parseInt(channelEl.dataset.channelId, 10) : null;
            if (!channelId) {
                notification.add("Cannot detect Discuss channel — open a channel first", { type: "warning" });
                return;
            }
            ev.preventDefault();
            ev.stopPropagation();
            ta.value = "";
            try {
                await orm.call("kob.poll", "create_from_command", [], {
                    channel_id: channelId,
                    question,
                    options,
                });
                notification.add("Poll posted", { type: "success" });
            } catch (e) {
                notification.add("Poll creation failed: " + (e.message || e), { type: "danger" });
            }
        }, true);
    },
};

registry.category("services").add("kob_discuss_polls.slash_command", slashCommandService);
