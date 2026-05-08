# -*- coding: utf-8 -*-
"""MEA cost calculator — pure functions, no DB writes."""
from odoo import api, models

VAT_RATE = 0.07


class MeaCalculator(models.AbstractModel):
    _name = "mea.calculator"
    _description = "MEA Bill Calculator (stateless)"

    @api.model
    def _compute_expected(self, meter, billing_date, kwh_data):
        """Compute expected MEA bill amount.

        Args:
            meter: ``mea.meter`` recordset (size 1) or dict-like with
                   ``tariff_id``.
            billing_date: ``date`` of the billing month.
            kwh_data: dict with keys ``total``, ``on_peak``, ``off_peak``.

        Returns:
            dict with keys ``energy``, ``demand``, ``service``, ``ft``,
            ``subtotal``, ``vat``, ``total``, ``kwh``, ``ft_rate_satang``.
        """
        tariff = meter.tariff_id if hasattr(meter, "tariff_id") else meter["tariff_id"]
        ft_period = self.env["mea.ft.period"].get_for_date(billing_date)
        ft_rate_satang = ft_period.ft_rate if ft_period else 0.0
        ft_thb_per_kwh = ft_rate_satang / 100.0

        total_kwh = kwh_data.get("total") or 0.0
        on_peak = kwh_data.get("on_peak") or 0.0
        off_peak = kwh_data.get("off_peak") or 0.0

        if tariff.is_tou:
            # When peak/off-peak split is missing, estimate from typical TOU
            # commercial profile (~70% on-peak / ~30% off-peak based on KK16/KK2
            # historical bills). User can override later by editing the record.
            if not (on_peak or off_peak) and total_kwh:
                on_peak = total_kwh * 0.70
                off_peak = total_kwh * 0.30
            energy = on_peak * (tariff.peak_rate or 0.0) + off_peak * (tariff.off_peak_rate or 0.0)
            kwh_for_ft = (on_peak + off_peak) or total_kwh
        else:
            energy = self._compute_progressive_energy(tariff, total_kwh)
            kwh_for_ft = total_kwh

        ft_amount = kwh_for_ft * ft_thb_per_kwh
        service = tariff.service_charge or 0.0

        # Demand charge (TOU only). When demand_kw not provided, estimate from
        # on-peak kWh and a typical 8h business-day usage pattern over 22
        # working days (~176 on-peak hours/month). Empirically calibrated against
        # KK16 bills: actual_demand ≈ on_peak_kwh / 150 (load factor ~80%).
        demand_kw = kwh_data.get("demand_kw") or 0.0
        if not demand_kw and tariff.is_tou and on_peak:
            demand_kw = on_peak / 150.0
        demand = demand_kw * (tariff.demand_charge or 0.0) if tariff.is_tou else 0.0

        subtotal = energy + service + demand + ft_amount
        vat = subtotal * VAT_RATE
        total = subtotal + vat

        return {
            "energy": energy,
            "demand": demand,
            "service": service,
            "ft": ft_amount,
            "subtotal": subtotal,
            "vat": vat,
            "total": total,
            "kwh": kwh_for_ft,
            "ft_rate_satang": ft_rate_satang,
        }

    @api.model
    def _compute_progressive_energy(self, tariff, total_kwh):
        """Apply progressive tier rates for non-TOU tariffs (e.g. 1.1.x).

        Falls back to ``tariff.flat_rate`` when no tiers are configured.
        For tariff 2.1.2 (small business flat) MEA charges fixed per-tier
        amounts (not multiplied by kWh) — modelled here as ``rate`` x bracket
        size to mirror the printed bill structure.
        """
        if not tariff.tier_ids:
            return total_kwh * (tariff.flat_rate or 0.0)

        remaining = total_kwh
        energy = 0.0
        for tier in tariff.tier_ids.sorted(key=lambda t: t.kwh_from):
            if remaining <= 0:
                break
            bracket = (tier.kwh_to - tier.kwh_from) if tier.kwh_to else remaining
            consumed = min(remaining, bracket)
            energy += consumed * tier.rate
            remaining -= consumed
        return energy
