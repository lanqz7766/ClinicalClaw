from __future__ import annotations

from clinicalclaw.config import ClinicalClawSettings
from clinicalclaw.connectors.base import ConnectorBundle, ConnectorMode
from clinicalclaw.connectors.fhir import SmartFHIRConnector
from clinicalclaw.connectors.imaging import DICOMWebConnector


def build_connector_bundle(settings: ClinicalClawSettings) -> ConnectorBundle:
    ehr_mode = ConnectorMode(settings.ehr_connector_mode)
    imaging_mode = ConnectorMode(settings.imaging_connector_mode)
    return ConnectorBundle(
        ehr=SmartFHIRConnector(
            mode=ehr_mode,
            base_url=settings.fhir_base_url,
            access_token=settings.fhir_access_token,
            authorize_url=settings.fhir_authorize_url,
            token_url=settings.fhir_token_url,
            client_id=settings.fhir_client_id,
            client_secret=settings.fhir_client_secret,
            redirect_uri=settings.fhir_redirect_uri,
            scope=settings.fhir_scope,
            timeout_s=settings.connector_timeout_s,
        ),
        imaging=DICOMWebConnector(
            mode=imaging_mode,
            base_url=settings.dicomweb_base_url,
            access_token=settings.dicomweb_access_token,
            timeout_s=settings.connector_timeout_s,
        ),
    )
