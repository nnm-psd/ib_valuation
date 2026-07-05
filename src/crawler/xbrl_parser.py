"""
Parse an ESEF zip package into a flat list of raw XBRL facts using Arelle
(the open-source XBRL processor -- this is the workhorse that does the
actual iXBRL tag extraction, so we never need an LLM to "read" the filing).

Arelle's Python API is a bit clunky (it's built around its own CntlrCmdLine
controller), so this module wraps it into a clean, simple function.
"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory


@dataclass
class XbrlFact:
    concept: str       # e.g. "ifrs-full:Revenue"
    value: float | str
    context_period: str  # e.g. "2023-01-01/2023-12-31" or instant date
    unit: str | None
    decimals: str | None


def parse_esef_package(zip_path: Path) -> list[XbrlFact]:
    """
    Extract all tagged facts from an ESEF report package.

    Implementation note: Arelle is invoked via its Cntlr API. The exact
    import path can vary by Arelle version -- if `from arelle import Cntlr`
    fails, check `pip show arelle-release` and consult Arelle's API docs.
    """
    from arelle import Cntlr  # noqa: WPS433 (deliberate local import -- heavy lib)

    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(tmp_path)

        # Find the primary XHTML/iXBRL report inside the extracted package
        report_candidates = list(tmp_path.rglob("*.xhtml")) + list(tmp_path.rglob("*.html"))
        if not report_candidates:
            raise FileNotFoundError(f"No iXBRL report file found inside {zip_path}")
        report_file = report_candidates[0]

        controller = Cntlr.Cntlr(logFileName=None)
        model_xbrl = controller.modelManager.load(str(report_file))

        facts: list[XbrlFact] = []
        for fact in model_xbrl.facts:
            try:
                facts.append(
                    XbrlFact(
                        concept=str(fact.concept.qname) if fact.concept is not None else "unknown",
                        value=fact.value,
                        context_period=_describe_period(fact.context),
                        unit=str(fact.unit.value) if fact.unit is not None else None,
                        decimals=fact.decimals,
                    )
                )
            except Exception:  # noqa: BLE001 -- some facts (e.g. text blocks) aren't numeric, skip safely
                continue

        controller.close()
        return facts


def _describe_period(context) -> str:
    if context is None:
        return "unknown"
    if context.isInstantPeriod:
        return str(context.instantDatetime)
    return f"{context.startDatetime}/{context.endDatetime}"
