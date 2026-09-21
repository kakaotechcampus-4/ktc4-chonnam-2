# 등록 원본의 현재 AssetFacts 조회

Owner: 정철원. 기존 `lookup_asset_facts({kind, ref})`를 로컬 등록 원본에 연결한다.
Canonical 근거는 `contract-source-asset-media-stream.md` §6이다.

```powershell
uv run --locked python -m examples.recording_source_facts <로컬영상>
```

root Python 3.12 환경과 ffprobe가 필요하다. 예제는 등록 후 공개 lookup을 호출해
AssetFacts JSON만 출력한다. 원본이나 파생 파일을 저장하지 않는다.

## 판정 규칙

매 조회에서 파일을 읽어 등록 당시 SHA-256·크기·수정 시각과 대조한다.
등록 당시 SourceAsset을 갱신하거나 이전 AssetFacts를 덮어쓰지 않는다.

| 관찰 | 반환 |
| --- | --- |
| 등록 snapshot과 일치 | AVAILABLE, 확인된 크기, 등록 시 probe한 duration |
| 소실·일반 파일이 아닌 대상으로 교체·내용 또는 수정 시각 변경 | UNAVAILABLE, byte_size/duration_sec=null |
| 권한·IO 오류 또는 읽는 도중 변경 | TEMPORARY_FAILURE, stale 성공값 반환 금지 |
| 미등록 ref | UNKNOWN_REF |
| 조회 대상이 아닌 kind | INVALID_REF_KIND |

`checked_at`은 검사를 마친 UTC offset-aware 시각이다. 파일을 다시 probe하지 않으며,
동일 snapshot임을 확인한 경우에만 등록 시 duration을 재사용한다. 전체 stream decode
가능성을 보증하지 않으며 MediaStream.availability는 바꾸지 않는다.

SOURCE_ASSET의 외부 부모가 없으면 lineage=[]이다. 이는 부모를 모른다는 뜻이 아니라
현재 로컬 등록이 외부 부모 ref를 생성하지 않았다는 사실이다. 외부 부모가 있는 내부
SourceAsset에는 그 external_source ref를 전달한다.

Source ref에는 여러 Timeline을 생성할 수 있으므로 lookup에서 임의로 최신 Timeline을
선택하지 않는다. timeline_ref와 timeline_range는 모두 null이다. 이는 원본 사실 조회이며
IncidentClip coverage를 대체하지 않는다. Case·Evidence의 coverage 정책은 변경하지 않는다.

## 한계 및 후속 단위

조회마다 원본 전체 hash를 읽는 비용이 있다. 관찰은 checked_at 시점 기준이며 이후 변경을
방지하는 파일 잠금은 제공하지 않는다. 수정 시각만 바뀌어도 등록 identity가 달라진 것으로
보수적으로 판정한다. 변경된 파일의 새 metadata가 필요하면 새로 등록한다.

fixture 조회는 기존대로 유지한다. 파생 자산의 실제 AssetFacts, span 매핑,
AnalysisSource·IncidentClip 생성은 후속 단위다. D1/D2/D3나 미확정 profile을 변경하지 않는다.

`tests/recording/test_local_asset_facts.py`는 생성 영상과 opt-in 실제 영상으로 계약·원본 보존을
검증한다. 파일 소실·동일 크기/수정 시각을 유지한 내용 변경·IO 실패 테스트는 임시 파일에만 적용한다.
