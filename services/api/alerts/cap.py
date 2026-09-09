"""CAP (Common Alerting Protocol) generation.

Generates CAP-compliant XML payloads for landslide warnings.
Supports geo-fencing and multi-language output (English, Hindi, Assamese).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4


@dataclass
class CapAlert:
    """A CAP alert payload."""
    id: str
    cap_xml: str
    severity: int  # 0-4 (IMD ladder)
    headline: str
    description: str
    geofence: list[tuple[float, float]] | None  # List of (lat, lon) tuples
    languages: list[str]
    trigger_src: str  # risk_band | deformation | report | manual
    issued_at: datetime
    expires_at: datetime


_SEVERITY_MAP = {
    0: ("Unknown", "Minor"),
    1: ("Watch", "Moderate"),
    2: ("Alert", "Severe"),
    3: ("Warning", "Extreme"),
    4: ("Severe", "Extreme"),
}

# Language codes (ISO 639-1)
_SUPPORTED_LANGUAGES = ["en", "hi", "as"]


def generate_cap_xml(
    identifier: str,
    sender: str,
    sent: datetime,
    headline: str,
    description: str,
    severity: str,
    status: str = "Actual",
    msg_type: str = "Alert",
    scope: str = "Public",
    urgency: str = "Expected",
    certainty: str = "Likely",
    effective: datetime | None = None,
    expires: datetime | None = None,
    area_desc: str | None = None,
    polygon_coords: list[tuple[float, float]] | None = None,
    language: str = "en",
) -> str:
    """Generate a CAP XML document.

    Args:
        identifier: Unique identifier for the alert
        sender: Originator of the alert
        sent: Time the alert was sent
        status: Status of the alert (Actual | Exercise | System | Test | Draft)
        msg_type: Type of the alert (Alert | Update | Cancel | Ack | Error)
        scope: Scope of the alert (Public | Restricted | Private | Limited)
        headline: Brief headline for the alert
        description: Full description of the alert
        severity: Severity level (Extreme | Severe | Moderate | Minor | Unknown)
        urgency: Urgency level (Immediate | Expected | Future | Past | Unknown)
        certainty: Certainty level (Observed | Likely | Possible | Unlikely | Unknown)
        effective: Effective time of the alert
        expires: Expiration time of the alert
        area_desc: Description of the affected area
        polygon_coords: List of (lat, lon) tuples defining the geofence polygon
        language: Language code (en | hi | as)

    Returns:
        CAP XML string
    """
    effective_str = effective.strftime("%Y-%m-%dT%H:%M:%S%z") if effective else sent.strftime("%Y-%m-%dT%H:%M:%S%z")
    expires_str = expires.strftime("%Y-%m-%dT%H:%M:%S%z") if expires else (sent + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S%z")
    sent_str = sent.strftime("%Y-%m-%dT%H:%M:%S%z")

    polygon_xml = ""
    if polygon_coords:
        # Convert (lat, lon) to "lat,lon lat,lon ..." format for CAP
        coord_str = " ".join([f"{lat},{lon}" for lat, lon in polygon_coords])
        polygon_xml = f"""
        <area>
            <areaDesc>{area_desc or "Affected area"}</areaDesc>
            <polygon>{coord_str}</polygon>
        </area>
        """

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
    <identifier>{identifier}</identifier>
    <sender>{sender}</sender>
    <sent>{sent_str}</sent>
    <status>{status}</status>
    <msgType>{msg_type}</msgType>
    <scope>{scope}</scope>
    <info>
        <language>{language}</language>
        <category>Geo</category>
        <event>Landslide Warning</event>
        <severity>{severity}</severity>
        <urgency>{urgency}</urgency>
        <certainty>{certainty}</certainty>
        <effective>{effective_str}</effective>
        <expires>{expires_str}</expires>
        <headline>{headline}</headline>
        <description>{description}</description>
        {polygon_xml}
    </info>
</alert>
"""
    return xml.strip()


def generate_landslide_alert(
    risk_band: int,
    area_name: str,
    geofence: list[tuple[float, float]] | None = None,
    trigger_src: str = "risk_band",
    language: str = "en",
    issued_at: datetime | None = None,
    expires_hours: int = 24,
) -> CapAlert:
    """Generate a landslide alert based on risk band.

    Args:
        risk_band: Risk band (0-4) from the IMD warning ladder
        area_name: Name of the affected area
        geofence: Polygon defining the affected area
        trigger_src: Source of the trigger (risk_band | deformation | report | manual)
        language: Language code (en | hi | as)
        issued_at: Time the alert was issued
        expires_hours: Hours until the alert expires

    Returns:
        CapAlert object with XML payload
    """
    if language not in _SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language: {language}. Supported: {_SUPPORTED_LANGUAGES}")

    if issued_at is None:
        issued_at = datetime.now()

    expires_at = issued_at + timedelta(hours=expires_hours)

    # Map risk band to CAP severity
    cap_severity, headline_severity = _SEVERITY_MAP.get(risk_band, ("Unknown", "Minor"))

    # Generate localized content
    if language == "en":
        headline = f"{headline_severity} Landslide Risk - {area_name}"
        description = (
            f"Landslide risk level {risk_band} detected in {area_name}. "
            f"Residents in affected areas should take immediate precautions. "
            f"Avoid steep slopes and areas with recent slope movement. "
            f"Follow official instructions from local authorities."
        )
    elif language == "hi":
        headline = f"{headline_severity} भूस्खलन जोखिम - {area_name}"
        description = (
            f"{area_name} में भूस्खलन जोखिम स्तर {risk_band} का पता चला है। "
            f"प्रभावित क्षेत्रों के निवासियों को तत्काल सावधानी बरतनी चाहिए। "
            f"खड़ी ढलानों और हाल के ढलान आंदोलन वाले क्षेत्रों से बचें। "
            f"स्थानीय अधिकारियों के आधिकारिक निर्देशों का पालन करें।"
        )
    elif language == "as":
        headline = f"{headline_severity} ভূস্খলনৰ আশংকা - {area_name}"
        description = (
            f"{area_name}-ত ভূস্খলনৰ আশংকা স্তৰ {risk_band} চিনাকি দিয়া হৈছে। "
            f"প্ৰভাৱিত অঞ্চলৰ বাসিন্দাসকলে তৎক্ষণাৎ সাৱধানতা অৱলম্বন কৰিব লাগিব। "
            f"খড়ী ঢাল আৰু শেহতীয়া ঢাল আন্দোলন থকা অঞ্চলৰ পৰা আঁতৰি থাকক। "
            f"স্থানীয় কৰ্তৃপক্ষৰ আধিকাৰিক নিৰ্দেশ অনুসৰণ কৰক।"
        )
    else:
        # Fallback to English
        headline = f"{headline_severity} Landslide Risk - {area_name}"
        description = f"Landslide risk level {risk_band} detected in {area_name}."

    # Convert polygon to CAP format
    polygon_coords = geofence  # Already in (lat, lon) format

    alert_id = str(uuid4())
    cap_xml = generate_cap_xml(
        identifier=alert_id,
        sender="Q-ResQ NER",
        sent=issued_at,
        headline=headline,
        description=description,
        severity=cap_severity,
        effective=issued_at,
        expires=expires_at,
        area_desc=area_name,
        polygon_coords=polygon_coords,
        language=language,
    )

    return CapAlert(
        id=alert_id,
        cap_xml=cap_xml,
        severity=risk_band,
        headline=headline,
        description=description,
        geofence=polygon_coords,
        languages=[language],
        trigger_src=trigger_src,
        issued_at=issued_at,
        expires_at=expires_at,
    )


def generate_deformation_alert(
    corridor_id: str,
    area_name: str,
    geofence: list[tuple[float, float]] | None = None,
    language: str = "en",
    issued_at: datetime | None = None,
) -> CapAlert:
    """Generate an alert based on InSAR deformation acceleration.

    Args:
        corridor_id: ID of the InSAR corridor with accelerating points
        area_name: Name of the affected area
        geofence: Polygon defining the affected area
        language: Language code (en | hi | as)
        issued_at: Time the alert was issued

    Returns:
        CapAlert object with XML payload
    """
    if issued_at is None:
        issued_at = datetime.now()

    # Deformation alerts are always high severity
    risk_band = 3  # Warning level

    if language == "en":
        headline = f"Ground Movement Detected - {area_name}"
        description = (
            f"Accelerating ground movement detected in {area_name} "
            f"via satellite interferometry. This indicates active slope instability. "
            f"Residents in the affected corridor should evacuate immediately. "
            f"Do not wait for visual confirmation of slope failure."
        )
    elif language == "hi":
        headline = f"भूमि आंदोलन का पता चला - {area_name}"
        description = (
            f"{area_name} में उपग्रह इंटरफेरोमेट्री के माध्यम से त्वरित भूमि आंदोलन का पता चला है। "
            f"यह सक्रिय ढलान अस्थिरता का संकेत देता है। "
            f"प्रभावित गलियारे के निवासियों को तुरंत खाली कर देना चाहिए। "
            f"ढलान विफलता की दृश्य पुष्टि की प्रतीक्षा न करें।"
        )
    elif language == "as":
        headline = f"মাটিৰ চলন চিনাকি দিয়া হৈছে - {area_name}"
        description = (
            f"{area_name}-ত উপগ্ৰহ ইণ্টাৰফেৰোমেট্ৰিৰ জৰিয়তে ত্বৰিত মাটিৰ চলন চিনাকি দিয়া হৈছে। "
            f"ই সক্ৰিয় ঢাল অস্থিৰতাৰ সংকেত দিয়ে। "
            f"প্ৰভাৱিত কৰিডৰৰ বাসিন্দাসকলে তৎক্ষণাৎ খালী কৰিব লাগিব। "
            f"ঢাল বিফলতাৰ দৃশ্য নিশ্চিতকৰণৰ অপেক্ষা নকৰিব।"
        )
    else:
        headline = f"Ground Movement Detected - {area_name}"
        description = f"Accelerating ground movement detected in {area_name}."

    polygon_coords = geofence  # Already in (lat, lon) format

    alert_id = str(uuid4())
    cap_xml = generate_cap_xml(
        identifier=alert_id,
        sender="Q-ResQ NER",
        sent=issued_at,
        headline=headline,
        description=description,
        severity="Extreme",
        effective=issued_at,
        expires=issued_at + timedelta(hours=12),  # Deformation alerts expire sooner
        area_desc=area_name,
        polygon_coords=polygon_coords,
        language=language,
    )

    return CapAlert(
        id=alert_id,
        cap_xml=cap_xml,
        severity=risk_band,
        headline=headline,
        description=description,
        geofence=polygon_coords,
        languages=[language],
        trigger_src="deformation",
        issued_at=issued_at,
        expires_at=issued_at + timedelta(hours=12),
    )
