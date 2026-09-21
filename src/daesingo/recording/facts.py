"""등록된 로컬 원본 identity를 재검증하여 현재 자산 사실을 만든다."""

from datetime import datetime, timezone

from .errors import RecordingCapabilityError
from .models import AssetFacts, ContractRef, SourceAsset
from .probe import LocalSource, _snapshot


def inspect_local_source(asset: SourceAsset, local: LocalSource) -> AssetFacts:
    try:
        snapshot = _snapshot(local.path)
        available = (snapshot[2], snapshot[3], snapshot[4]) == (
            local.byte_size, local.mtime_ns, local.sha256,
        )
    except (FileNotFoundError, NotADirectoryError, ValueError):
        # 원본 소실 또는 일반 파일이 아닌 대상으로 교체됨. 등록 이력은 유지한다.
        available = False
    except OSError:
        # 권한/IO 오류만으로 원본 부재나 내용 변경을 단정하지 않는다.
        raise RecordingCapabilityError("TEMPORARY_FAILURE", "원본의 현재 상태를 확인할 수 없습니다") from None
    lineage = []
    if asset.external_source_ref is not None:
        lineage.append(ContractRef(kind="external_source", ref=asset.external_source_ref.ref))
    return AssetFacts(
        contract="AssetFacts", contract_version="source-asset-media-stream/v1",
        asset_ref=ContractRef(kind="source_asset", ref=asset.source_asset_ref),
        asset_kind="SOURCE_ASSET", derived_role=None,
        byte_size=local.byte_size if available else None,
        availability="AVAILABLE" if available else "UNAVAILABLE",
        checked_at=datetime.now(timezone.utc), lineage=lineage,
        duration_sec=local.duration_sec if available else None,
        # source ref 하나에 여러 Timeline을 생성할 수 있다. 임의로 최신 것을 고르지 않는다.
        timeline_ref=None, timeline_range=None,
    )
