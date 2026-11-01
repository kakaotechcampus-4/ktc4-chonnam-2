"""P-6 internal public capability; not a serialized product Contract."""
from enum import Enum
import re


class PublishRegistration(Enum):
    REGISTERED = 'REGISTERED'
    UNREGISTERED = 'UNREGISTERED'
    UNKNOWN = 'UNKNOWN'


def managed_publish_locator(locator):
    return isinstance(locator, str) and re.fullmatch(r'source/[0-9a-f]{32}', locator) is not None


def registration_from_payloads(locator, payloads):
    """Unknown spellings may alias a candidate; never interpret them as absent.

    Ignore root_key differences deliberately: different processes/OS spellings
    may refer to the same mounted root. This can overprotect, never underprotect.
    """
    if not managed_publish_locator(locator):
        return PublishRegistration.UNKNOWN
    uncertain = False
    for payload in payloads:
        stored = payload.get('locator') if isinstance(payload, dict) else None
        if stored == locator:
            return PublishRegistration.REGISTERED
        if not managed_publish_locator(stored):
            uncertain = True
    return PublishRegistration.UNKNOWN if uncertain else PublishRegistration.UNREGISTERED
