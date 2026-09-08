# 03. Mock Artifact Templates

아래 모든 JSON 예시는 손으로 다시 쓴 것이 아니라 `data/mock/` 아래 실제로 생성된 fixture 파일에서 그대로 발췌했다(`scripts/build_artifact_templates_doc.py`가 기계적으로 추출). 문서와 실제 fixture가 갈라질 수 없다.

## recording

### SourceAsset (정상)

**Contract**: `source-asset-media-stream/v1`  
**출처**: recording/scenario_happy_001.json → source_assets[0] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "SourceAsset",
  "contract_version": "source-asset-media-stream/v1",
  "source_asset_ref": "sa_h001_front",
  "asset_kind": "SOURCE_ASSET",
  "external_source_ref": {
    "kind": "external_source",
    "ref": "ext_h001_front"
  },
  "media_stream_refs": [
    "ms_h001_front_v",
    "ms_h001_front_a"
  ],
  "byte_size": 734003200,
  "availability": "AVAILABLE",
  "duration_sec": 1200.0
}
```

### RecordingTimeline (USABLE)

**Contract**: `recording-timeline/v1`  
**출처**: recording/scenario_happy_001.json → recording_timelines[0] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "RecordingTimeline",
  "contract_version": "recording-timeline/v1",
  "timeline_id": "tl_h001",
  "revision": 1,
  "time_basis": {
    "mode": "ABSOLUTE_AND_RELATIVE",
    "working_anchor": {
      "value": "2026-08-24T18:00:00+09:00",
      "source_candidate_ref": "tsc_h001_filename",
      "status": "OK"
    }
  },
  "time_source_candidates": [
    "tsc_h001_filename"
  ],
  "source_placements": [
    {
      "source_asset_ref": "sa_h001_front",
      "timeline_start_sec": 0.0,
      "timeline_end_sec": 1200.0,
      "media_stream_refs": [
        "ms_h001_front_v",
        "ms_h001_front_a"
      ]
    },
    {
      "source_asset_ref": "sa_h001_rear",
      "timeline_start_sec": 0.0,
      "timeline_end_sec": 1200.0,
      "media_stream_refs": [
        "ms_h001_rear_v"
      ]
    }
  ],
  "gaps": [],
  "timeline_status": "USABLE",
  "produced_by": "recording"
}
```

### IncidentClip

**Contract**: `analysis-source-derived/v1`  
**출처**: recording/scenario_happy_001.json → incident_clips[0] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "IncidentClip",
  "contract_version": "analysis-source-derived/v1",
  "incident_clip_ref": "clip_h001",
  "asset_kind": "INCIDENT_CLIP",
  "source_provenance": {
    "timeline_ref": {
      "timeline_id": "tl_h001",
      "revision": 1
    },
    "requested_range": {
      "start_sec": 300.0,
      "end_sec": 420.0
    },
    "asset_spans": [
      {
        "sequence": 0,
        "timeline_range": {
          "start_sec": 300.0,
          "end_sec": 420.0
        },
        "source_asset_ref": "sa_h001_front",
        "media_stream_ref": "ms_h001_front_v",
        "source_range": {
          "start_sec": 300.0,
          "end_sec": 420.0
        }
      }
    ]
  },
  "media_stream_refs": [
    "ms_h001_front_v"
  ],
  "byte_size": 36700160,
  "availability": "AVAILABLE",
  "duration_sec": 120.0,
  "timeline_ref": {
    "timeline_id": "tl_h001",
    "revision": 1
  },
  "timeline_range": {
    "start_sec": 300.0,
    "end_sec": 420.0
  }
}
```

### TimeSourceCandidate ×2 (충돌하는 두 시각 후보)

**Contract**: `recording-timeline/v1`  
**출처**: recording/scenario_unknown_abstain_partial_001.json → time_source_candidates (실제 파일에서 그대로 발췌)

```json
[
  {
    "candidate_id": "tsc_u001_filename",
    "source_kind": "FILENAME",
    "source_detail": "MDR_260826_221000.AVI",
    "value": "2026-08-26T22:10:00+09:00",
    "applies_to": {
      "source_asset_ref": "sa_u001",
      "source_offset_sec": 0.0
    },
    "observation_status": "OK",
    "producer_checks": {
      "parse_valid": true
    },
    "provenance": {
      "producer": "recording",
      "observed_from": "MDR_260826_221000.AVI"
    }
  },
  {
    "candidate_id": "tsc_u001_filemeta",
    "source_kind": "FILE_METADATA",
    "source_detail": "container creation_time atom",
    "value": "2026-08-26T22:13:00+09:00",
    "applies_to": {
      "source_asset_ref": "sa_u001",
      "source_offset_sec": 0.0
    },
    "observation_status": "OK",
    "producer_checks": {
      "parse_valid": true
    },
    "provenance": {
      "producer": "recording",
      "observed_from": "container metadata"
    }
  }
]
```

## search

### AnalysisRun + CandidateEvent (정상, 후보 1건)

**Contract**: `analysis-run-candidate-event/v1.1`  
**출처**: search/scenario_happy_001.json → analysis_run_candidate_events[0] (실제 파일에서 그대로 발췌)

```json
{
  "analysis_run": {
    "run_id": "run_h001",
    "operation": "CANDIDATE_SEARCH",
    "input_ref": {
      "kind": "ANALYSIS_SCOPE",
      "ref": "scope_h001"
    },
    "implementation": {
      "impl_id": "gemini-candidate-search@c7",
      "model_ref": "gemini-3.7-flash",
      "prompt_version": "coarse-c7",
      "config_version": "search-v2"
    },
    "outcome": "SUCCEEDED",
    "started_at": "2026-08-24T18:20:05+09:00",
    "completed_at": "2026-08-24T18:21:10+09:00",
    "issues": [],
    "usage_refs": [
      "usage_h001_coarse"
    ],
    "usage_summary": {
      "processed_duration_ms": 1200000,
      "token_usage": {
        "input_tokens": 14200,
        "output_tokens": 1200,
        "total_tokens": 15400
      },
      "latency_ms": 65000,
      "total_cost": {
        "amount": "0.42",
        "currency": "USD"
      }
    },
    "contract_version": "analysis-run-candidate-event/v1.1"
  },
  "candidates": [
    {
      "candidate_id": "candidate_h001",
      "run_id": "run_h001",
      "span": {
        "timeline_id": "tl_h001",
        "timeline_revision": 1,
        "start_ms": 300000,
        "end_ms": 420000,
        "representative_ms": 312480
      },
      "rank": 1,
      "ranking_score": 0.86,
      "event_type_hint": "SOLID_LINE_LANE_CHANGE",
      "summary": "흰 SUV가 백색 실선을 넘어 인접 차로로 이동하는 장면",
      "uncertainties": [],
      "thumbnail_ref": "fr_h001_thumb"
    }
  ]
}
```

### VisualEvidence

**Contract**: `visual-evidence/v1.0`  
**출처**: search/scenario_happy_001.json → visual_evidences[0] (실제 파일에서 그대로 발췌)

```json
{
  "schema_version": "visual-evidence/v1.0",
  "visual_evidence_id": "ve_h001",
  "run_id": "run_h001",
  "input_ref": {
    "kind": "incident_clip",
    "ref": "clip_h001"
  },
  "candidate_id": "candidate_h001",
  "verification": "OBSERVED",
  "visual_event_type": "SOLID_LINE_LANE_CHANGE",
  "target": {
    "association_status": "MATCHED",
    "described_as": "흰색 SUV",
    "match_with_hint": true,
    "association_confidence": 0.84,
    "track_ref": null,
    "evidence_refs": [
      "fr_h001_thumb"
    ]
  },
  "primitives": [
    {
      "kind": "WHITE_SOLID_LINE",
      "state": "PRESENT",
      "confidence": 0.9,
      "evidence_refs": [
        "fr_h001_thumb"
      ]
    }
  ],
  "temporal_facts": [
    {
      "at_offset_ms": 12480,
      "fact": "TARGET_CROSSES_LINE",
      "evidence_refs": [
        "fr_h001_thumb"
      ]
    }
  ],
  "uncertainties": [],
  "legal_status": null
}
```

### AnalysisRun — 결과 없음(candidates=[], outcome=SUCCEEDED)

**Contract**: `analysis-run-candidate-event/v1.1`  
**출처**: search/scenario_empty_001.json → analysis_run_candidate_events[0] (실제 파일에서 그대로 발췌)

```json
{
  "analysis_run": {
    "run_id": "run_e001",
    "operation": "CANDIDATE_SEARCH",
    "input_ref": {
      "kind": "ANALYSIS_SCOPE",
      "ref": "scope_e001"
    },
    "implementation": {
      "impl_id": "gemini-candidate-search@c7",
      "model_ref": "gemini-3.7-flash",
      "prompt_version": "coarse-c7",
      "config_version": "search-v2"
    },
    "outcome": "SUCCEEDED",
    "started_at": "2026-08-25T07:30:05+09:00",
    "completed_at": "2026-08-25T07:31:02+09:00",
    "issues": [],
    "usage_refs": [
      "usage_e001_coarse"
    ],
    "usage_summary": {
      "processed_duration_ms": 1800000,
      "token_usage": {
        "input_tokens": 9800,
        "output_tokens": 420,
        "total_tokens": 10220
      },
      "latency_ms": 57000,
      "total_cost": {
        "amount": "0.31",
        "currency": "USD"
      }
    },
    "contract_version": "analysis-run-candidate-event/v1.1"
  },
  "candidates": []
}
```

## readout

### PlateReadout (정상, abstain 없음)

**Contract**: `plate-readout/v1.2`  
**출처**: readout/scenario_happy_001.json → plate_readouts[0] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "PlateReadout",
  "contract_version": "plate-readout/v1.2",
  "readout_id": "readout_h001_plate",
  "run_ref": {
    "kind": "readout_run",
    "ref": "rr_h001_plate"
  },
  "case_id": "case_h001",
  "candidate_id": "candidate_h001",
  "input_ref": {
    "incident_clip_ref": "clip_h001",
    "source_profile": "readout-native",
    "provenance": "SOURCE_DERIVED_INCIDENT_CLIP"
  },
  "target_association": {
    "status": "ASSOCIATED",
    "target_hint_used": true,
    "track_ref": "track_h001",
    "association_method": "TARGET_HINT_WITH_FALLBACK",
    "associated_region": {
      "frame_ref": "fr_h001_plate1",
      "bbox_xywh": [
        820,
        410,
        176,
        68
      ]
    },
    "evidence": [
      {
        "kind": "SPATIAL_PROXIMITY",
        "detail": "candidate target region overlaps selected track"
      },
      {
        "kind": "MULTI_FRAME_CONTINUITY",
        "detail": "similar plate crop appears across sampled frames"
      }
    ]
  },
  "observation": {
    "contract_version": "observation/v1",
    "value": "12가3456",
    "status": "OK",
    "source": {
      "kind": "readout.plate_ocr"
    },
    "support_refs": [],
    "produced_by": {
      "module": "readout",
      "run_ref": {
        "kind": "readout_run",
        "ref": "rr_h001_plate"
      }
    }
  },
  "consensus": {
    "text": "12가3456",
    "disagree_positions": [],
    "method": "MULTI_FRAME"
  },
  "abstained": false,
  "abstain_reason": null,
  "best_frame": {
    "frame_ref": "fr_h001_plate1",
    "crop_ref": "crop_h001_001",
    "quality": {
      "plate_px_height": 44,
      "sharpness": 0.87
    }
  },
  "frame_results": [
    {
      "frame_ref": "fr_h001_plate1",
      "crop_ref": "crop_h001_001",
      "text": "12가3456",
      "confidence": 0.91
    },
    {
      "frame_ref": "fr_h001_plate2",
      "crop_ref": "crop_h001_002",
      "text": "12가3456",
      "confidence": 0.88
    }
  ]
}
```

### OverlayTimeReadout (정상)

**Contract**: `overlay-time-readout/v1.2`  
**출처**: readout/scenario_happy_001.json → overlay_time_readouts[0] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "OverlayTimeReadout",
  "contract_version": "overlay-time-readout/v1.2",
  "readout_id": "readout_h001_overlay",
  "run_ref": {
    "kind": "readout_run",
    "ref": "rr_h001_overlay"
  },
  "case_id": "case_h001",
  "candidate_id": "candidate_h001",
  "input_ref": {
    "incident_clip_ref": "clip_h001",
    "source_profile": "readout-native",
    "provenance": "SOURCE_DERIVED_INCIDENT_CLIP"
  },
  "observation": {
    "contract_version": "observation/v1",
    "value": "2026-08-24T18:05:12+09:00",
    "status": "OK",
    "source": {
      "kind": "readout.overlay_ocr"
    },
    "support_refs": [],
    "produced_by": {
      "module": "readout",
      "run_ref": {
        "kind": "readout_run",
        "ref": "rr_h001_overlay"
      }
    }
  },
  "validation": {
    "format_ok": true,
    "monotonic_ok": true,
    "duration_match_ok": true,
    "sample_count": 3
  },
  "samples": [
    {
      "frame_ref": "fr_h001_thumb",
      "offset_sec": 12.48,
      "raw_text": "2026-08-24 18:05:12",
      "parsed_at": "2026-08-24T18:05:12+09:00"
    },
    {
      "frame_ref": "fr_h001_plate1",
      "offset_sec": 13.1,
      "raw_text": "2026-08-24 18:05:13",
      "parsed_at": "2026-08-24T18:05:13+09:00"
    },
    {
      "frame_ref": "fr_h001_plate2",
      "offset_sec": 13.6,
      "raw_text": "2026-08-24 18:05:13",
      "parsed_at": "2026-08-24T18:05:13+09:00"
    }
  ]
}
```

### PlateReadout — ABSTAIN (target_association=AMBIGUOUS)

**Contract**: `plate-readout/v1.2`  
**출처**: readout/scenario_unknown_abstain_partial_001.json → plate_readouts[0] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "PlateReadout",
  "contract_version": "plate-readout/v1.2",
  "readout_id": "readout_u001_plate",
  "run_ref": {
    "kind": "readout_run",
    "ref": "rr_u001_plate"
  },
  "case_id": "case_u001",
  "candidate_id": "candidate_u001",
  "input_ref": {
    "incident_clip_ref": "clip_u001",
    "source_profile": "readout-native",
    "provenance": "SOURCE_DERIVED_INCIDENT_CLIP"
  },
  "target_association": {
    "status": "AMBIGUOUS",
    "target_hint_used": true,
    "track_ref": null,
    "association_method": "TARGET_HINT_WITH_FALLBACK",
    "associated_region": {
      "frame_ref": "fr_u001_plate1",
      "bbox_xywh": [
        640,
        500,
        96,
        40
      ]
    },
    "evidence": [
      {
        "kind": "SPATIAL_PROXIMITY",
        "detail": "two candidate regions overlap similarly with selected track"
      }
    ]
  },
  "observation": {
    "contract_version": "observation/v1",
    "value": "17나28?4",
    "status": "NEEDS_REVIEW",
    "source": {
      "kind": "readout.plate_ocr"
    },
    "support_refs": [],
    "produced_by": {
      "module": "readout",
      "run_ref": {
        "kind": "readout_run",
        "ref": "rr_u001_plate"
      }
    }
  },
  "consensus": {
    "text": "17나28?4",
    "disagree_positions": [
      5
    ],
    "method": "MULTI_FRAME"
  },
  "abstained": true,
  "abstain_reason": "FRAME_DISAGREEMENT",
  "best_frame": {
    "frame_ref": "fr_u001_plate1",
    "crop_ref": "crop_u001_001",
    "quality": {
      "plate_px_height": 24,
      "sharpness": 0.44
    }
  },
  "frame_results": [
    {
      "frame_ref": "fr_u001_plate1",
      "crop_ref": "crop_u001_001",
      "text": "17나2804",
      "confidence": 0.41
    },
    {
      "frame_ref": "fr_u001_plate2",
      "crop_ref": "crop_u001_002",
      "text": "17나2894",
      "confidence": 0.38
    }
  ]
}
```

### ReadoutRun — 완전 실패 (결과 객체 자체가 생성되지 않음)

**Contract**: `readout-run/v1`  
**출처**: readout/scenario_unknown_abstain_partial_001.json → readout_runs[1] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "ReadoutRun",
  "contract_version": "readout-run/v1",
  "run_id": "rr_u001_overlay",
  "operation": "OVERLAY_TIME_READ",
  "outcome": "FAILED",
  "failure": {
    "kind": "OVERLAY_DETECTION",
    "code": "NO_OVERLAY_PRESENT"
  },
  "usage_refs": [
    "usage_u001_overlay"
  ],
  "started_at": "2026-08-26T22:32:08+09:00",
  "ended_at": "2026-08-26T22:32:11+09:00"
}
```

## evidence

### TimeResolution (status=OK, 검증된 Overlay)

**Contract**: `time-resolution/v1`  
**출처**: evidence/scenario_happy_001.json → time_resolutions[0] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "TimeResolution",
  "contract_version": "time-resolution/v1",
  "resolution_ref": {
    "kind": "time_resolution",
    "ref": "tres_h001"
  },
  "status": "OK",
  "resolved": {
    "value": "2026-08-24T18:05:12+09:00",
    "source": {
      "kind": "readout.overlay_ocr",
      "input_ref": {
        "kind": "overlay_time_readout",
        "ref": "readout_h001_overlay"
      }
    },
    "verification": "VERIFIED",
    "computation": {
      "mode": "DIRECT",
      "timezone": {
        "zone_id": "Asia/Seoul",
        "utc_offset": "+09:00",
        "source": "PRODUCT_CONTEXT"
      }
    },
    "user_corrected": false
  },
  "considered": [
    {
      "input_kind": "OBSERVATION",
      "input_ref": {
        "kind": "overlay_time_readout",
        "ref": "readout_h001_overlay"
      },
      "source": {
        "kind": "readout.overlay_ocr"
      },
      "value": "2026-08-24T18:05:12+09:00",
      "observation_status": "OK",
      "verification": "VERIFIED",
      "used": true
    },
    {
      "input_kind": "OBSERVATION",
      "input_ref": {
        "kind": "time_source_candidate",
        "ref": "tsc_h001_filename"
      },
      "source": {
        "kind": "recording.filename_time"
      },
      "value": "2026-08-24T18:00:00+09:00",
      "observation_status": "OK",
      "verification": "UNVERIFIED",
      "used": false,
      "reason_code": "time.superseded_by_verified_overlay"
    }
  ],
  "conflict": {
    "exists": false,
    "between_refs": [],
    "requires_user_notice": false
  },
  "provenance": {
    "policy_ref": "policy/time-source-priority-v1",
    "selected_input_ref": {
      "kind": "overlay_time_readout",
      "ref": "readout_h001_overlay"
    }
  },
  "post_stamp": {
    "needed": false,
    "reason_code": "time.verified_overlay_already_present",
    "requires_user_notice": false
  }
}
```

### EvidenceRecord (모든 값 confirmed)

**Contract**: `evidence-record/v1.2`  
**출처**: evidence/scenario_happy_001.json → evidence_records[0] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "EvidenceRecord",
  "contract_version": "evidence-record/v1.2",
  "record_ref": {
    "kind": "evidence_record",
    "ref": "ev_h001"
  },
  "case_ref": {
    "kind": "case",
    "ref": "case_h001"
  },
  "selection_rev": 1,
  "basis": {
    "candidate_ref": {
      "kind": "candidate_event",
      "ref": "candidate_h001"
    },
    "visual_evidence_ref": {
      "kind": "visual_evidence",
      "ref": "ve_h001"
    },
    "evidence_interval_ref": {
      "kind": "incident_clip",
      "ref": "clip_h001"
    }
  },
  "event": {
    "visual_event_type": {
      "value": "SOLID_LINE_LANE_CHANGE",
      "source": {
        "kind": "search.visual_inference",
        "ref": {
          "kind": "visual_evidence",
          "ref": "ve_h001"
        },
        "observability": "OBSERVED",
        "label_key": "event.source.visual_inference"
      },
      "support_refs": [
        {
          "kind": "visual_evidence",
          "ref": "ve_h001"
        }
      ],
      "user_corrected": false,
      "needs_review": false
    },
    "safety_report_type": {
      "value": "UNSAFE_LANE_CHANGE",
      "source": {
        "kind": "evidence.category_mapping",
        "ref": {
          "kind": "visual_evidence",
          "ref": "ve_h001"
        },
        "observability": "INFERRED",
        "label_key": "event.source.category_mapping"
      },
      "support_refs": [
        {
          "kind": "visual_evidence",
          "ref": "ve_h001"
        }
      ],
      "user_corrected": false,
      "needs_review": false
    },
    "violation_expression": {
      "value": "흰색 SUV가 편도 2차로 도로에서 백색 실선 구간을 가로질러 차로를 변경함",
      "source": {
        "kind": "evidence.violation_expression",
        "ref": {
          "kind": "visual_evidence",
          "ref": "ve_h001"
        },
        "observability": "INFERRED",
        "label_key": "event.source.violation_expression"
      },
      "support_refs": [
        {
          "kind": "visual_evidence",
          "ref": "ve_h001"
        }
      ],
      "user_corrected": false,
      "needs_review": false
    }
  },
  "occurred_at": {
    "value": "2026-08-24T18:05:12+09:00",
    "time_resolution_ref": {
      "kind": "time_resolution",
      "ref": "tres_h001"
    },
    "resolution_status": "OK",
    "user_corrected": false,
    "source": {
      "kind": "readout.overlay_ocr",
      "label_key": "time.source.overlay_ocr"
    }
  },
  "vehicle_number": {
    "value": "12가3456",
    "source": {
      "kind": "readout.plate_ocr",
      "ref": {
        "kind": "plate_readout",
        "ref": "readout_h001_plate"
      },
      "observability": "OBSERVED",
      "label_key": "plate.source.plate_ocr"
    },
    "support_refs": [
      {
        "kind": "plate_readout",
        "ref": "readout_h001_plate"
      }
    ],
    "user_corrected": false,
    "needs_review": false
  },
  "location": {
    "search_keyword": {
      "value": "광주 상무지구 상무중앙로 사거리",
      "source": {
        "kind": "case.user_location_hint",
        "ref": {
          "kind": "case",
          "ref": "case_h001"
        },
        "observability": "OBSERVED",
        "label_key": "location.source.user_hint"
      },
      "support_refs": [],
      "user_corrected": false,
      "needs_review": false
    },
    "user_hint": {
      "value": "상무중앙로에서 시청 방향으로 가다가 사거리에서 발생",
      "source": {
        "kind": "case.user_location_hint",
        "ref": {
          "kind": "case",
          "ref": "case_h001"
        },
        "observability": "OBSERVED",
        "label_key": "location.source.user_hint"
      },
      "support_refs": [],
      "user_corrected": false,
      "needs_review": false
    }
  },
  "provenance": {
    "input_refs": [
      {
        "kind": "visual_evidence",
        "ref": "ve_h001"
      },
      {
        "kind": "plate_readout",
        "ref": "readout_h001_plate"
      },
      {
        "kind": "overlay_time_readout",
        "ref": "readout_h001_overlay"
      },
      {
        "kind": "time_resolution",
        "ref": "tres_h001"
      }
    ],
    "correction_refs": [],
    "policy_ref": "policy/evidence-assembly-v1"
  }
}
```

### RequirementReport (scope=FINAL_PACKAGE, overall=PASS)

**Contract**: `requirement-report/v1`  
**출처**: evidence/scenario_happy_001.json → requirement_reports[1] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "RequirementReport",
  "contract_version": "requirement-report/v1",
  "requirement_report_ref": {
    "kind": "requirement_report",
    "ref": "req_h001_final"
  },
  "scope": "FINAL_PACKAGE",
  "basis": {
    "evidence_record_ref": {
      "kind": "evidence_record",
      "ref": "ev_h001"
    },
    "asset_refs": [
      {
        "kind": "derived_asset",
        "ref": "da_h001_report_video"
      },
      {
        "kind": "derived_asset",
        "ref": "da_h001_plate_image"
      }
    ],
    "template_ref": "tmpl/safety-report-v1"
  },
  "policy_ref": "policy/requirement-rules-v1",
  "evaluated_at": "2026-08-24T18:25:00+09:00",
  "overall": "PASS",
  "checks": [
    {
      "code": "package.asset.report_video.exists",
      "category": "ASSET",
      "outcome": "PASS",
      "reason_code": "asset.available",
      "subject_refs": [
        {
          "kind": "derived_asset",
          "ref": "da_h001_report_video"
        }
      ],
      "measurement": {
        "actual": 120.0,
        "limit": 180.0,
        "unit": "asset.duration_sec"
      }
    },
    {
      "code": "package.asset.plate_visible",
      "category": "ASSET",
      "outcome": "PASS",
      "reason_code": "asset.plate_legible",
      "subject_refs": [
        {
          "kind": "derived_asset",
          "ref": "da_h001_plate_image"
        }
      ]
    },
    {
      "code": "package.time.overlay_visible",
      "category": "TIME",
      "outcome": "PASS",
      "reason_code": "time.overlay_burned_in",
      "subject_refs": [
        {
          "kind": "derived_asset",
          "ref": "da_h001_report_video"
        }
      ]
    }
  ]
}
```

### ReportPackage

**Contract**: `report-package/v1`  
**출처**: evidence/scenario_happy_001.json → report_packages[0] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "ReportPackage",
  "contract_version": "report-package/v1",
  "package_ref": {
    "kind": "report_package",
    "ref": "pkg_h001"
  },
  "evidence_record_ref": {
    "kind": "evidence_record",
    "ref": "ev_h001"
  },
  "requirement_report_ref": {
    "kind": "requirement_report",
    "ref": "req_h001_final"
  },
  "created_at": "2026-08-24T18:26:00+09:00",
  "report_inputs": {
    "safety_report_type": "안전운전 불이행",
    "occurred_at": "2026-08-24T18:05:12+09:00",
    "location": {
      "display_text": "상무중앙로에서 시청 방향으로 가다가 사거리에서 발생",
      "search_keyword": "광주 상무지구 상무중앙로 사거리"
    },
    "vehicle_number": "12가3456",
    "violation_expression": "흰색 SUV가 편도 2차로 도로에서 백색 실선 구간을 가로질러 차로를 변경함"
  },
  "report": {
    "title": "백색 실선 구간 차로변경 위반 신고",
    "description": "2026-08-24 18:05:12 광주 상무지구 상무중앙로 사거리 인근에서 차량번호 12가3456 차량이 백색 실선 구간에서 차로를 변경하였습니다.",
    "template_ref": "tmpl/safety-report-v1"
  },
  "assets": {
    "report_video_ref": {
      "kind": "derived_asset",
      "ref": "da_h001_report_video"
    },
    "plate_image_ref": {
      "kind": "derived_asset",
      "ref": "da_h001_plate_image"
    }
  },
  "provenance": {
    "source_refs": [
      {
        "kind": "source_asset",
        "ref": "sa_h001_front"
      }
    ],
    "derived_asset_refs": [
      {
        "kind": "derived_asset",
        "ref": "da_h001_report_video"
      },
      {
        "kind": "derived_asset",
        "ref": "da_h001_plate_image"
      }
    ],
    "policy_ref": "policy/package-assembly-v1"
  },
  "handoff": {
    "destination": "SAFETY_REPORT",
    "supported_actions": [
      "DOWNLOAD_ASSETS",
      "COPY_FIELDS",
      "OPEN_DESTINATION"
    ]
  }
}
```

### TimeResolution — 값 충돌 보존 (conflict.exists=true, status=NEEDS_REVIEW)

**Contract**: `time-resolution/v1`  
**출처**: evidence/scenario_unknown_abstain_partial_001.json → time_resolutions[0] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "TimeResolution",
  "contract_version": "time-resolution/v1",
  "resolution_ref": {
    "kind": "time_resolution",
    "ref": "tres_u001"
  },
  "status": "NEEDS_REVIEW",
  "resolved": {
    "value": "2026-08-26T22:20:15+09:00",
    "source": {
      "kind": "recording.filename_time",
      "input_ref": {
        "kind": "time_source_candidate",
        "ref": "tsc_u001_filename"
      }
    },
    "verification": "UNVERIFIED",
    "computation": {
      "mode": "BASE_PLUS_OFFSET",
      "base_input_ref": {
        "kind": "time_source_candidate",
        "ref": "tsc_u001_filename"
      },
      "source_offset_ms": 615000,
      "timezone": {
        "zone_id": "Asia/Seoul",
        "utc_offset": "+09:00",
        "source": "PRODUCT_CONTEXT"
      }
    },
    "user_corrected": false
  },
  "considered": [
    {
      "input_kind": "OBSERVATION",
      "input_ref": {
        "kind": "time_source_candidate",
        "ref": "tsc_u001_filename"
      },
      "source": {
        "kind": "recording.filename_time"
      },
      "value": "2026-08-26T22:10:00+09:00",
      "observation_status": "OK",
      "verification": "UNVERIFIED",
      "used": true
    },
    {
      "input_kind": "OBSERVATION",
      "input_ref": {
        "kind": "time_source_candidate",
        "ref": "tsc_u001_filemeta"
      },
      "source": {
        "kind": "recording.file_metadata_time"
      },
      "value": "2026-08-26T22:13:00+09:00",
      "observation_status": "OK",
      "verification": "UNVERIFIED",
      "used": false,
      "reason_code": "time.conflicting_metadata_candidate"
    }
  ],
  "conflict": {
    "exists": true,
    "between_refs": [
      {
        "kind": "time_source_candidate",
        "ref": "tsc_u001_filename"
      },
      {
        "kind": "time_source_candidate",
        "ref": "tsc_u001_filemeta"
      }
    ],
    "requires_user_notice": true
  },
  "provenance": {
    "policy_ref": "policy/time-source-priority-v1",
    "selected_input_ref": {
      "kind": "time_source_candidate",
      "ref": "tsc_u001_filename"
    }
  },
  "post_stamp": {
    "needed": true,
    "reason_code": "time.no_verified_overlay_present",
    "requires_user_notice": true
  }
}
```

### EvidenceRecord — vehicle_number 필드 자체 부재(UNKNOWN)

**Contract**: `evidence-record/v1.2`  
**출처**: evidence/scenario_unknown_abstain_partial_001.json → evidence_records[0] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "EvidenceRecord",
  "contract_version": "evidence-record/v1.2",
  "record_ref": {
    "kind": "evidence_record",
    "ref": "ev_u001"
  },
  "case_ref": {
    "kind": "case",
    "ref": "case_u001"
  },
  "selection_rev": 1,
  "basis": {
    "candidate_ref": {
      "kind": "candidate_event",
      "ref": "candidate_u001"
    },
    "visual_evidence_ref": {
      "kind": "visual_evidence",
      "ref": "ve_u001"
    },
    "evidence_interval_ref": {
      "kind": "incident_clip",
      "ref": "clip_u001"
    }
  },
  "event": {
    "visual_event_type": {
      "value": "SIGNAL",
      "source": {
        "kind": "search.visual_inference",
        "ref": {
          "kind": "visual_evidence",
          "ref": "ve_u001"
        },
        "observability": "OBSERVED",
        "label_key": "event.source.visual_inference"
      },
      "support_refs": [
        {
          "kind": "visual_evidence",
          "ref": "ve_u001"
        }
      ],
      "user_corrected": false,
      "needs_review": true
    },
    "safety_report_type": {
      "value": "UNSAFE_SIGNAL_VIOLATION",
      "source": {
        "kind": "evidence.category_mapping",
        "ref": {
          "kind": "visual_evidence",
          "ref": "ve_u001"
        },
        "observability": "INFERRED",
        "label_key": "event.source.category_mapping"
      },
      "support_refs": [
        {
          "kind": "visual_evidence",
          "ref": "ve_u001"
        }
      ],
      "user_corrected": false,
      "needs_review": true
    },
    "violation_expression": {
      "value": "은색 해치백이 신호를 위반하고 정지선을 통과한 것으로 추정됨 (신호 상태 확인 필요)",
      "source": {
        "kind": "evidence.violation_expression",
        "ref": {
          "kind": "visual_evidence",
          "ref": "ve_u001"
        },
        "observability": "INFERRED",
        "label_key": "event.source.violation_expression"
      },
      "support_refs": [
        {
          "kind": "visual_evidence",
          "ref": "ve_u001"
        }
      ],
      "user_corrected": false,
      "needs_review": true
    }
  },
  "occurred_at": {
    "value": "2026-08-26T22:20:15+09:00",
    "time_resolution_ref": {
      "kind": "time_resolution",
      "ref": "tres_u001"
    },
    "resolution_status": "NEEDS_REVIEW",
    "user_corrected": false,
    "source": {
      "kind": "recording.filename_time",
      "label_key": "time.source.filename"
    }
  },
  "provenance": {
    "input_refs": [
      {
        "kind": "visual_evidence",
        "ref": "ve_u001"
      },
      {
        "kind": "plate_readout",
        "ref": "readout_u001_plate"
      },
      {
        "kind": "time_resolution",
        "ref": "tres_u001"
      }
    ],
    "correction_refs": [],
    "policy_ref": "policy/evidence-assembly-v1"
  }
}
```

### EvidenceNeeds — PLATE_REREAD 요청

**Contract**: `evidence-needs/v1`  
**출처**: evidence/scenario_unknown_abstain_partial_001.json → evidence_needs[0] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "EvidenceNeeds",
  "contract_version": "evidence-needs/v1",
  "basis_record_ref": {
    "kind": "evidence_record",
    "ref": "ev_u001"
  },
  "items": [
    {
      "kind": "PLATE_REREAD",
      "would_fill": "VEHICLE_NUMBER",
      "why": {
        "code": "readout.plate_abstained_ambiguous_target",
        "summary": "번호판 관찰이 대상 차량 식별 모호 및 프레임 간 불일치로 보류됨"
      },
      "optional": false,
      "context_refs": [
        {
          "role": "evidence.interval",
          "ref": {
            "kind": "incident_clip",
            "ref": "clip_u001"
          }
        },
        {
          "role": "evidence.target_hint",
          "ref": {
            "kind": "visual_evidence",
            "ref": "ve_u001"
          }
        }
      ]
    }
  ]
}
```

### RequirementReport — overall=UNKNOWN

**Contract**: `requirement-report/v1`  
**출처**: evidence/scenario_unknown_abstain_partial_001.json → requirement_reports[0] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "RequirementReport",
  "contract_version": "requirement-report/v1",
  "requirement_report_ref": {
    "kind": "requirement_report",
    "ref": "req_u001_evidence"
  },
  "scope": "EVIDENCE",
  "basis": {
    "evidence_record_ref": {
      "kind": "evidence_record",
      "ref": "ev_u001"
    },
    "asset_refs": []
  },
  "policy_ref": "policy/requirement-rules-v1",
  "evaluated_at": "2026-08-26T22:33:00+09:00",
  "overall": "UNKNOWN",
  "checks": [
    {
      "code": "evidence.vehicle_number.present",
      "category": "VEHICLE",
      "outcome": "UNKNOWN",
      "reason_code": "evidence.pending_plate_reread",
      "subject_refs": [
        {
          "kind": "evidence_record",
          "ref": "ev_u001"
        }
      ]
    },
    {
      "code": "evidence.occurred_at.present",
      "category": "TIME",
      "outcome": "WARN",
      "reason_code": "evidence.time_needs_review",
      "subject_refs": [
        {
          "kind": "evidence_record",
          "ref": "ev_u001"
        }
      ]
    },
    {
      "code": "evidence.visual_event.present",
      "category": "EVIDENCE",
      "outcome": "WARN",
      "reason_code": "evidence.signal_state_uncertain",
      "subject_refs": [
        {
          "kind": "evidence_record",
          "ref": "ev_u001"
        }
      ]
    }
  ]
}
```

### TimeResolution v2 — USER_OVERRIDE, supersedes_ref

**Contract**: `time-resolution/v1`  
**출처**: evidence/scenario_correction_rerun_001.json → time_resolutions[1] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "TimeResolution",
  "contract_version": "time-resolution/v1",
  "resolution_ref": {
    "kind": "time_resolution",
    "ref": "tres_r001_v2"
  },
  "supersedes_ref": {
    "kind": "time_resolution",
    "ref": "tres_r001_v1"
  },
  "status": "OK",
  "resolved": {
    "value": "2026-08-27T13:13:00+09:00",
    "source": {
      "kind": "case.user_correction",
      "input_ref": {
        "kind": "correction_record",
        "ref": "cr_r001_time"
      }
    },
    "verification": "AGREED",
    "computation": {
      "mode": "USER_OVERRIDE",
      "timezone": {
        "zone_id": "Asia/Seoul",
        "utc_offset": "+09:00",
        "source": "PRODUCT_CONTEXT"
      }
    },
    "user_corrected": true
  },
  "considered": [
    {
      "input_kind": "USER_INPUT",
      "input_ref": {
        "kind": "correction_record",
        "ref": "cr_r001_time"
      },
      "source": {
        "kind": "case.user_correction"
      },
      "value": "2026-08-27T13:13:00+09:00",
      "verification": "AGREED",
      "used": true
    },
    {
      "input_kind": "OBSERVATION",
      "input_ref": {
        "kind": "time_source_candidate",
        "ref": "tsc_r001_filename"
      },
      "source": {
        "kind": "recording.filename_time"
      },
      "value": "2026-08-27T13:00:00+09:00",
      "observation_status": "OK",
      "verification": "UNVERIFIED",
      "used": false,
      "reason_code": "time.superseded_by_user_correction"
    }
  ],
  "conflict": {
    "exists": false,
    "between_refs": [],
    "requires_user_notice": false
  },
  "provenance": {
    "policy_ref": "policy/time-source-priority-v1",
    "selected_input_ref": {
      "kind": "correction_record",
      "ref": "cr_r001_time"
    }
  },
  "post_stamp": {
    "needed": true,
    "reason_code": "time.user_confirmed_no_overlay_present",
    "requires_user_notice": true
  }
}
```

### EvidenceRecord v2 — supersede, vehicle_number 값 리셋 없이 그대로 유지

**Contract**: `evidence-record/v1.2`  
**출처**: evidence/scenario_correction_rerun_001.json → evidence_records[1] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "EvidenceRecord",
  "contract_version": "evidence-record/v1.2",
  "record_ref": {
    "kind": "evidence_record",
    "ref": "ev_r001_v2"
  },
  "supersedes_ref": {
    "kind": "evidence_record",
    "ref": "ev_r001_v1"
  },
  "case_ref": {
    "kind": "case",
    "ref": "case_r001"
  },
  "selection_rev": 2,
  "basis": {
    "candidate_ref": {
      "kind": "candidate_event",
      "ref": "candidate_r001"
    },
    "visual_evidence_ref": {
      "kind": "visual_evidence",
      "ref": "ve_r001"
    },
    "evidence_interval_ref": {
      "kind": "incident_clip",
      "ref": "clip_r001"
    }
  },
  "event": {
    "visual_event_type": {
      "value": "MOTORCYCLE_HELMET_NON_USE",
      "source": {
        "kind": "search.visual_inference",
        "ref": {
          "kind": "visual_evidence",
          "ref": "ve_r001"
        },
        "observability": "OBSERVED",
        "label_key": "event.source.visual_inference"
      },
      "support_refs": [
        {
          "kind": "visual_evidence",
          "ref": "ve_r001"
        }
      ],
      "user_corrected": false,
      "needs_review": false
    },
    "safety_report_type": {
      "value": "UNSAFE_HELMET_NON_USE",
      "source": {
        "kind": "evidence.category_mapping",
        "ref": {
          "kind": "visual_evidence",
          "ref": "ve_r001"
        },
        "observability": "INFERRED",
        "label_key": "event.source.category_mapping"
      },
      "support_refs": [
        {
          "kind": "visual_evidence",
          "ref": "ve_r001"
        }
      ],
      "user_corrected": false,
      "needs_review": false
    },
    "violation_expression": {
      "value": "이륜차 운전자가 안전모를 착용하지 않은 상태로 주행함",
      "source": {
        "kind": "evidence.violation_expression",
        "ref": {
          "kind": "visual_evidence",
          "ref": "ve_r001"
        },
        "observability": "INFERRED",
        "label_key": "event.source.violation_expression"
      },
      "support_refs": [
        {
          "kind": "visual_evidence",
          "ref": "ve_r001"
        }
      ],
      "user_corrected": false,
      "needs_review": false
    }
  },
  "occurred_at": {
    "value": "2026-08-27T13:13:00+09:00",
    "time_resolution_ref": {
      "kind": "time_resolution",
      "ref": "tres_r001_v2"
    },
    "resolution_status": "OK",
    "user_corrected": true,
    "source": {
      "kind": "case.user_correction",
      "label_key": "time.source.user_correction"
    }
  },
  "vehicle_number": {
    "value": "광주서구 가1234",
    "source": {
      "kind": "readout.plate_ocr",
      "ref": {
        "kind": "plate_readout",
        "ref": "readout_r001_plate"
      },
      "observability": "OBSERVED",
      "label_key": "plate.source.plate_ocr"
    },
    "support_refs": [
      {
        "kind": "plate_readout",
        "ref": "readout_r001_plate"
      }
    ],
    "user_corrected": false,
    "needs_review": false
  },
  "provenance": {
    "input_refs": [
      {
        "kind": "visual_evidence",
        "ref": "ve_r001"
      },
      {
        "kind": "plate_readout",
        "ref": "readout_r001_plate"
      },
      {
        "kind": "time_resolution",
        "ref": "tres_r001_v2"
      }
    ],
    "correction_refs": [
      {
        "kind": "correction_record",
        "ref": "cr_r001_time"
      }
    ],
    "policy_ref": "policy/evidence-assembly-v1"
  }
}
```

## case

### JobRecord (COARSE_SEARCH)

**Contract**: `job-record/v1`  
**출처**: case/scenario_happy_001.json → job_records[0] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "JobRecord",
  "contract_version": "job-record/v1",
  "job_id": "job_h001_search",
  "case_id": "case_h001",
  "case_rev": 1,
  "kind": "COARSE_SEARCH",
  "scope_ref": "scope_h001",
  "input_fingerprint": "sha1:h001-coarse-search",
  "force_rerun": false,
  "requested_at": "2026-08-24T18:20:04+09:00"
}
```

### CaseView — 처리 중 (stage=SEARCHING, progress RUNNING/PENDING)

**Contract**: `case-view/v1.2`  
**출처**: case/scenario_happy_001.json → case_views[0] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "CaseView",
  "contract_version": "case-view/v1.2",
  "case_id": "case_h001",
  "case_rev": 1,
  "stage": "SEARCHING",
  "user_reviewed": false,
  "manifest_summary": {
    "file_count": 2,
    "ok_file_count": 2,
    "failed_file_count": 0,
    "duration_sec": 1200.0,
    "range": [
      "2026-08-24T18:00:00+09:00",
      "2026-08-24T18:20:00+09:00"
    ]
  },
  "hints": {
    "time": "18시쯤",
    "vehicle": "흰색 SUV",
    "situation": "백색 실선 구간에서 차로변경",
    "location": "상무중앙로 사거리 부근"
  },
  "progress": [
    {
      "step": "file_intake",
      "state": "DONE"
    },
    {
      "step": "coarse_search",
      "state": "RUNNING"
    },
    {
      "step": "candidate_review",
      "state": "PENDING"
    },
    {
      "step": "plate_read",
      "state": "PENDING"
    },
    {
      "step": "overlay_time_read",
      "state": "PENDING"
    },
    {
      "step": "evidence_assembly",
      "state": "PENDING"
    },
    {
      "step": "requirement_check",
      "state": "PENDING"
    },
    {
      "step": "package_assembly",
      "state": "PENDING"
    }
  ],
  "candidates": [],
  "evidence": null,
  "requirements_evidence": null,
  "requirements_package": null,
  "package": null,
  "running_jobs": [
    {
      "job_id": "job_h001_search",
      "kind": "COARSE_SEARCH",
      "label_key": "job.generic_processing",
      "status": "RUNNING"
    }
  ],
  "notices": []
}
```

### CaseView (stage=READY)

**Contract**: `case-view/v1.2`  
**출처**: case/scenario_happy_001.json → case_views[1] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "CaseView",
  "contract_version": "case-view/v1.2",
  "case_id": "case_h001",
  "case_rev": 3,
  "stage": "READY",
  "user_reviewed": false,
  "manifest_summary": {
    "file_count": 2,
    "ok_file_count": 2,
    "failed_file_count": 0,
    "duration_sec": 1200.0,
    "range": [
      "2026-08-24T18:00:00+09:00",
      "2026-08-24T18:20:00+09:00"
    ]
  },
  "hints": {
    "time": "18시쯤",
    "vehicle": "흰색 SUV",
    "situation": "백색 실선 구간에서 차로변경",
    "location": "상무중앙로 사거리 부근"
  },
  "progress": [
    {
      "step": "file_intake",
      "state": "DONE"
    },
    {
      "step": "coarse_search",
      "state": "DONE"
    },
    {
      "step": "candidate_review",
      "state": "DONE"
    },
    {
      "step": "plate_read",
      "state": "DONE"
    },
    {
      "step": "overlay_time_read",
      "state": "DONE"
    },
    {
      "step": "evidence_assembly",
      "state": "DONE"
    },
    {
      "step": "requirement_check",
      "state": "DONE"
    },
    {
      "step": "package_assembly",
      "state": "DONE"
    }
  ],
  "candidates": [
    {
      "candidate_id": "candidate_h001",
      "at": "2026-08-24T18:05:12+09:00",
      "at_provenance": "readout.overlay_ocr",
      "observed": "흰 SUV가 백색 실선을 넘어 인접 차로로 이동하는 장면",
      "thumb_ref": "fr_h001_thumb",
      "selected": true
    }
  ],
  "evidence": {
    "record_id": "ev_h001",
    "case_type_display": {
      "code": "SOLID_LINE_LANE_CHANGE",
      "label": "백색 실선 구간 차로변경",
      "needs_review": false
    },
    "report_type_display": {
      "code": "UNSAFE_LANE_CHANGE",
      "label": "안전운전 불이행",
      "needs_review": false
    },
    "violation_display": {
      "code": null,
      "label": "흰색 SUV가 편도 2차로 도로에서 백색 실선 구간을 가로질러 차로를 변경함",
      "needs_review": false
    },
    "plate_display": {
      "value": "12가3456",
      "needs_review": false,
      "info_state": "INFO_SOURCE_VERIFIED",
      "source_label_key": "plate.source.plate_ocr"
    },
    "event_time_display": {
      "value": "2026-08-24T18:05:12+09:00",
      "needs_review": false,
      "info_state": "INFO_SOURCE_VERIFIED",
      "source_label_key": "time.source.overlay_ocr"
    },
    "location_display": {
      "value": "상무중앙로에서 시청 방향으로 가다가 사거리에서 발생",
      "needs_review": false,
      "info_state": "INFO_NEEDS_REVIEW",
      "source_label_key": "location.source.user_hint",
      "coord": null,
      "search_keyword": "광주 상무지구 상무중앙로 사거리"
    },
    "user_edited": false,
    "preview_ref": "fr_h001_thumb",
    "review_needed": false,
    "reason_code": null
  },
  "requirements_evidence": {
    "readiness": "PASS",
    "checks": [
      {
        "code": "evidence.vehicle_number.present",
        "outcome": "PASS",
        "reason_code": "evidence.value_confirmed"
      },
      {
        "code": "evidence.occurred_at.present",
        "outcome": "PASS",
        "reason_code": "evidence.value_confirmed"
      },
      {
        "code": "evidence.visual_event.present",
        "outcome": "PASS",
        "reason_code": "evidence.value_confirmed"
      },
      {
        "code": "evidence.location.present",
        "outcome": "PASS",
        "reason_code": "evidence.user_hint_sufficient"
      }
    ]
  },
  "requirements_package": {
    "readiness": "PASS",
    "checks": [
      {
        "code": "package.asset.report_video.exists",
        "outcome": "PASS",
        "reason_code": "asset.available"
      },
      {
        "code": "package.asset.plate_visible",
        "outcome": "PASS",
        "reason_code": "asset.plate_legible"
      },
      {
        "code": "package.time.overlay_visible",
        "outcome": "PASS",
        "reason_code": "time.overlay_burned_in"
      }
    ]
  },
  "package": {
    "package_ref": "pkg_h001",
    "report_fields": {
      "safety_report_type": "안전운전 불이행",
      "occurred_at": "2026-08-24T18:05:12+09:00",
      "location": "상무중앙로에서 시청 방향으로 가다가 사거리에서 발생",
      "vehicle_number": "12가3456",
      "violation_expression": "흰색 SUV가 편도 2차로 도로에서 백색 실선 구간을 가로질러 차로를 변경함"
    },
    "artifact_ref": "da_h001_report_video",
    "capabilities": [
      "DOWNLOAD_ASSETS",
      "COPY_FIELDS",
      "OPEN_DESTINATION"
    ],
    "warnings": []
  },
  "running_jobs": [],
  "notices": []
}
```

### CaseView — 사용자 최종 확인 완료 (user_reviewed=true)

**Contract**: `case-view/v1.2`  
**출처**: case/scenario_happy_001.json → case_views[2] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "CaseView",
  "contract_version": "case-view/v1.2",
  "case_id": "case_h001",
  "case_rev": 4,
  "stage": "READY",
  "user_reviewed": true,
  "manifest_summary": {
    "file_count": 2,
    "ok_file_count": 2,
    "failed_file_count": 0,
    "duration_sec": 1200.0,
    "range": [
      "2026-08-24T18:00:00+09:00",
      "2026-08-24T18:20:00+09:00"
    ]
  },
  "hints": {
    "time": "18시쯤",
    "vehicle": "흰색 SUV",
    "situation": "백색 실선 구간에서 차로변경",
    "location": "상무중앙로 사거리 부근"
  },
  "progress": [
    {
      "step": "file_intake",
      "state": "DONE"
    },
    {
      "step": "coarse_search",
      "state": "DONE"
    },
    {
      "step": "candidate_review",
      "state": "DONE"
    },
    {
      "step": "plate_read",
      "state": "DONE"
    },
    {
      "step": "overlay_time_read",
      "state": "DONE"
    },
    {
      "step": "evidence_assembly",
      "state": "DONE"
    },
    {
      "step": "requirement_check",
      "state": "DONE"
    },
    {
      "step": "package_assembly",
      "state": "DONE"
    }
  ],
  "candidates": [
    {
      "candidate_id": "candidate_h001",
      "at": "2026-08-24T18:05:12+09:00",
      "at_provenance": "readout.overlay_ocr",
      "observed": "흰 SUV가 백색 실선을 넘어 인접 차로로 이동하는 장면",
      "thumb_ref": "fr_h001_thumb",
      "selected": true
    }
  ],
  "evidence": {
    "record_id": "ev_h001",
    "case_type_display": {
      "code": "SOLID_LINE_LANE_CHANGE",
      "label": "백색 실선 구간 차로변경",
      "needs_review": false
    },
    "report_type_display": {
      "code": "UNSAFE_LANE_CHANGE",
      "label": "안전운전 불이행",
      "needs_review": false
    },
    "violation_display": {
      "code": null,
      "label": "흰색 SUV가 편도 2차로 도로에서 백색 실선 구간을 가로질러 차로를 변경함",
      "needs_review": false
    },
    "plate_display": {
      "value": "12가3456",
      "needs_review": false,
      "info_state": "INFO_SOURCE_VERIFIED",
      "source_label_key": "plate.source.plate_ocr"
    },
    "event_time_display": {
      "value": "2026-08-24T18:05:12+09:00",
      "needs_review": false,
      "info_state": "INFO_SOURCE_VERIFIED",
      "source_label_key": "time.source.overlay_ocr"
    },
    "location_display": {
      "value": "상무중앙로에서 시청 방향으로 가다가 사거리에서 발생",
      "needs_review": false,
      "info_state": "INFO_NEEDS_REVIEW",
      "source_label_key": "location.source.user_hint",
      "coord": null,
      "search_keyword": "광주 상무지구 상무중앙로 사거리"
    },
    "user_edited": false,
    "preview_ref": "fr_h001_thumb",
    "review_needed": false,
    "reason_code": null
  },
  "requirements_evidence": {
    "readiness": "PASS",
    "checks": [
      {
        "code": "evidence.vehicle_number.present",
        "outcome": "PASS",
        "reason_code": "evidence.value_confirmed"
      },
      {
        "code": "evidence.occurred_at.present",
        "outcome": "PASS",
        "reason_code": "evidence.value_confirmed"
      },
      {
        "code": "evidence.visual_event.present",
        "outcome": "PASS",
        "reason_code": "evidence.value_confirmed"
      },
      {
        "code": "evidence.location.present",
        "outcome": "PASS",
        "reason_code": "evidence.user_hint_sufficient"
      }
    ]
  },
  "requirements_package": {
    "readiness": "PASS",
    "checks": [
      {
        "code": "package.asset.report_video.exists",
        "outcome": "PASS",
        "reason_code": "asset.available"
      },
      {
        "code": "package.asset.plate_visible",
        "outcome": "PASS",
        "reason_code": "asset.plate_legible"
      },
      {
        "code": "package.time.overlay_visible",
        "outcome": "PASS",
        "reason_code": "time.overlay_burned_in"
      }
    ]
  },
  "package": {
    "package_ref": "pkg_h001",
    "report_fields": {
      "safety_report_type": "안전운전 불이행",
      "occurred_at": "2026-08-24T18:05:12+09:00",
      "location": "상무중앙로에서 시청 방향으로 가다가 사거리에서 발생",
      "vehicle_number": "12가3456",
      "violation_expression": "흰색 SUV가 편도 2차로 도로에서 백색 실선 구간을 가로질러 차로를 변경함"
    },
    "artifact_ref": "da_h001_report_video",
    "capabilities": [
      "DOWNLOAD_ASSETS",
      "COPY_FIELDS",
      "OPEN_DESTINATION"
    ],
    "warnings": []
  },
  "running_jobs": [],
  "notices": []
}
```

### JobRecord — 재판독 자동 발주 (kind=PLATE_READ, force_rerun=true)

**Contract**: `job-record/v1`  
**출처**: case/scenario_unknown_abstain_partial_001.json → job_records[3] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "JobRecord",
  "contract_version": "job-record/v1",
  "job_id": "job_u001_plate_reread",
  "case_id": "case_u001",
  "case_rev": 3,
  "kind": "PLATE_READ",
  "scope_ref": null,
  "input_fingerprint": "sha1:u001-plate-read-clip_u001",
  "force_rerun": true,
  "requested_at": "2026-08-26T22:33:05+09:00"
}
```

### CaseView — evidence.plate_display info_state=INFO_UNKNOWN, running_jobs 포함

**Contract**: `case-view/v1.2`  
**출처**: case/scenario_unknown_abstain_partial_001.json → case_views[0] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "CaseView",
  "contract_version": "case-view/v1.2",
  "case_id": "case_u001",
  "case_rev": 3,
  "stage": "EVIDENCE_REVIEW",
  "user_reviewed": false,
  "manifest_summary": {
    "file_count": 1,
    "ok_file_count": 1,
    "failed_file_count": 0,
    "duration_sec": 1800.0,
    "range": [
      "2026-08-26T22:10:00+09:00",
      "2026-08-26T22:40:00+09:00"
    ]
  },
  "hints": {
    "time": "밤 10시쯤",
    "vehicle": "은색 해치백",
    "situation": "신호 위반한 것 같은데 확실하지 않음",
    "location": null
  },
  "progress": [
    {
      "step": "file_intake",
      "state": "DONE"
    },
    {
      "step": "coarse_search",
      "state": "DONE"
    },
    {
      "step": "candidate_review",
      "state": "DONE"
    },
    {
      "step": "plate_read",
      "state": "DONE"
    },
    {
      "step": "overlay_time_read",
      "state": "FAILED"
    },
    {
      "step": "evidence_assembly",
      "state": "DONE"
    },
    {
      "step": "requirement_check",
      "state": "DONE"
    }
  ],
  "candidates": [
    {
      "candidate_id": "candidate_u001",
      "at": "2026-08-26T22:20:15+09:00",
      "at_provenance": "recording.filename_time",
      "observed": "은색 해치백이 정지선을 넘어 교차로를 통과하는 장면으로 추정됨",
      "thumb_ref": "fr_u001_plate1",
      "selected": true
    }
  ],
  "evidence": {
    "record_id": "ev_u001",
    "case_type_display": {
      "code": "SIGNAL",
      "label": "신호 위반 의심",
      "needs_review": true
    },
    "report_type_display": {
      "code": "UNSAFE_SIGNAL_VIOLATION",
      "label": "안전운전 불이행(신호위반 의심)",
      "needs_review": true
    },
    "violation_display": {
      "code": null,
      "label": "은색 해치백이 신호를 위반하고 정지선을 통과한 것으로 추정됨 (신호 상태 확인 필요)",
      "needs_review": true
    },
    "plate_display": {
      "value": null,
      "needs_review": false,
      "info_state": "INFO_UNKNOWN",
      "source_label_key": null
    },
    "event_time_display": {
      "value": "2026-08-26T22:20:15+09:00",
      "needs_review": true,
      "info_state": "INFO_NEEDS_REVIEW",
      "source_label_key": "time.source.filename"
    },
    "location_display": {
      "value": null,
      "needs_review": false,
      "info_state": "INFO_UNKNOWN",
      "source_label_key": null,
      "coord": null,
      "search_keyword": null
    },
    "user_edited": false,
    "preview_ref": "fr_u001_plate1",
    "review_needed": true,
    "reason_code": "evidence.multiple_fields_need_review"
  },
  "requirements_evidence": {
    "readiness": "UNKNOWN",
    "checks": [
      {
        "code": "evidence.vehicle_number.present",
        "outcome": "UNKNOWN",
        "reason_code": "evidence.pending_plate_reread"
      },
      {
        "code": "evidence.occurred_at.present",
        "outcome": "WARN",
        "reason_code": "evidence.time_needs_review"
      },
      {
        "code": "evidence.visual_event.present",
        "outcome": "WARN",
        "reason_code": "evidence.signal_state_uncertain"
      }
    ]
  },
  "requirements_package": null,
  "package": null,
  "running_jobs": [
    {
      "job_id": "job_u001_plate_reread",
      "kind": "PLATE_READ",
      "label_key": "job.plate_read",
      "status": "PENDING"
    }
  ],
  "notices": [
    {
      "code": "time.conflict_needs_notice",
      "severity": "WARN",
      "blocking": false,
      "message_key": "notice.time_conflict",
      "actions": [
        "REVIEW_TIME"
      ]
    },
    {
      "code": "evidence.plate_reread_in_progress",
      "severity": "INFO",
      "blocking": false,
      "message_key": "notice.plate_reread_running",
      "actions": []
    }
  ]
}
```

## common

### JobExecution (SUCCEEDED)

**Contract**: `job-execution/v1`  
**출처**: common/scenario_happy_001.json → job_executions[0] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "JobExecution",
  "contract_version": "job-execution/v1",
  "execution_id": "exec_h001_search",
  "job_id": "job_h001_search",
  "status": "SUCCEEDED",
  "attempt": 1,
  "queued_at": "2026-08-24T18:20:04+09:00",
  "started_at": "2026-08-24T18:20:05+09:00",
  "ended_at": "2026-08-24T18:21:10+09:00",
  "produced": [
    {
      "kind": "analysis_run",
      "ref": "run_h001"
    }
  ],
  "failure_kind": null,
  "usage_refs": [
    "usage_h001_coarse"
  ]
}
```

### UsageRecord (search 호출)

**Contract**: `usage-record/v1.1`  
**출처**: common/scenario_happy_001.json → usage_records[0] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "UsageRecord",
  "contract_version": "usage-record/v1.1",
  "usage_id": "usage_h001_coarse",
  "execution_ref": "exec_h001_search",
  "run_ref": {
    "kind": "analysis_run",
    "ref": "run_h001"
  },
  "case_id": "case_h001",
  "occurred_at": "2026-08-24T18:21:10+09:00",
  "provider_label": "gemini",
  "operation": "SEARCH_COARSE",
  "token_usage": {
    "input_tokens": 14200,
    "output_tokens": 1200,
    "total_tokens": 15400
  },
  "processed_duration_sec": 1200.0,
  "latency_ms": 65000,
  "pricing_context": {
    "pricing_id": "gemini-2026-08",
    "unit": "per_1k_tokens"
  },
  "cost": {
    "amount": "0.42",
    "currency": "USD"
  }
}
```

### JobExecution — QUEUED (재판독 대기 중, ended_at=null)

**Contract**: `job-execution/v1`  
**출처**: common/scenario_unknown_abstain_partial_001.json → job_executions[3] (실제 파일에서 그대로 발췌)

```json
{
  "contract": "JobExecution",
  "contract_version": "job-execution/v1",
  "execution_id": "exec_u001_plate_reread",
  "job_id": "job_u001_plate_reread",
  "status": "QUEUED",
  "attempt": 1,
  "queued_at": "2026-08-26T22:33:05+09:00",
  "started_at": null,
  "ended_at": null,
  "produced": [],
  "failure_kind": null,
  "usage_refs": []
}
```

## expected (Eval Harness, provisional — Final Contract 아님)

### Eval fixture — 항상 정답 (metric 계산 검증용)

**Contract**: `(provisional, non-contract)`  
**출처**: expected/eval_fixture_correct_001.json (전체) (실제 파일에서 그대로 발췌)

```json
{
  "eval_fixture_id": "eval_fixture_correct_001",
  "kind": "ALWAYS_CORRECT",
  "provisional_non_contract_schema": true,
  "note": "이 파일은 어떤 Final Data Contract도 소유하지 않는 Mock 전용 provisional 구조다. eval의 Ground Truth 스키마는 contract-readout-run.md §2 '정답지(READABLE+정답 문자열 / UNREADABLE)는 현재 없으며 eval 소유 후속'이라고 명시할 뿐 아직 확정되지 않았다. 이 fixture는 eval 팀이 자신의 metric 계산 코드를 최소한으로 검증할 수 있도록 제공하는 목적 전용이며, eval이 정식 Ground Truth Contract를 확정하면 교체되어야 한다.",
  "purpose": "actual == expected인 입력에서 metric 계산 코드 자체가 올바르게 1.0(만점)을 내는지 검증한다. Mock이 실제 AI 성능을 증명하는 용도가 아니다.",
  "scenario_ref": "scenario_happy_001",
  "case_id": "case_h001",
  "metric_targets": [
    {
      "metric": "plate_exact_match",
      "actual_ref": {
        "kind": "plate_readout",
        "ref": "readout_h001_plate"
      },
      "actual_value": "12가3456",
      "expected_value": "12가3456",
      "expect_match": true
    },
    {
      "metric": "candidate_top1_correct",
      "actual_ref": {
        "kind": "analysis_run_candidate_event",
        "ref": "run_h001"
      },
      "actual_top_candidate_id": "candidate_h001",
      "expected_top_candidate_id": "candidate_h001",
      "expect_match": true
    },
    {
      "metric": "occurred_at_within_tolerance",
      "actual_ref": {
        "kind": "time_resolution",
        "ref": "tres_h001"
      },
      "actual_value": "2026-08-24T18:05:12+09:00",
      "expected_value": "2026-08-24T18:05:12+09:00",
      "max_deviation_sec": 2,
      "expect_match": true
    },
    {
      "metric": "abstention_correctness",
      "actual_ref": {
        "kind": "plate_readout",
        "ref": "readout_h001_plate"
      },
      "actual_abstained": false,
      "expected_should_abstain": false,
      "expect_match": true
    }
  ],
  "expected_metric_results": {
    "plate_exact_match_rate": 1.0,
    "candidate_top1_accuracy": 1.0,
    "time_within_tolerance_rate": 1.0,
    "abstention_correctness_rate": 1.0
  }
}
```

### Eval fixture — 의도적 오답 (metric이 오류를 잡아내는지 검증용)

**Contract**: `(provisional, non-contract)`  
**출처**: expected/eval_fixture_wrong_001.json (전체) (실제 파일에서 그대로 발췌)

```json
{
  "eval_fixture_id": "eval_fixture_wrong_001",
  "kind": "DELIBERATELY_WRONG",
  "provisional_non_contract_schema": true,
  "note": "이 파일은 어떤 Final Data Contract도 소유하지 않는 Mock 전용 provisional 구조다(위와 동일한 사유 — eval Ground Truth Contract 미확정). eval의 metric 계산 코드가 실제로 오류를 잡아내는지 검증하는 용도이며, 이 fixture의 낮은 점수 자체가 시스템의 실제 성능을 뜻하지 않는다.",
  "actual_values_are_inline": "이 fixture의 actual_* 값은 의도적으로 틀리게 만든 합성값이며 런타임 fixture를 참조하지 않는다. actual_ref를 두면 harness가 역참조했을 때 실제(정답) 값이 나와 테스트가 통과해버리므로 참조를 두지 않는다. metric 이름은 eval Owner(김대원) 확정 대기 — docs/mock/05_mock_deep_review_report.md P1-11.",
  "purpose": "actual이 의도적으로 틀린 입력에서 metric 계산 코드가 만점을 내지 않고 실제로 오류를 검출하는지 검증한다 — bad candidate ranking, 큰 timestamp 편차, 잘못된 번호판 채택, false positive abstain을 각각 포함한다.",
  "scenario_ref": "scenario_happy_001(기대값 출처만 참조 — actual은 합성값)",
  "case_id": "case_h001",
  "metric_targets": [
    {
      "metric": "plate_exact_match",
      "actual_value": "98다6543",
      "expected_value": "12가3456",
      "expect_match": false,
      "defect": "WRONG_PLATE_ACCEPTED"
    },
    {
      "metric": "candidate_top1_correct",
      "actual_top_candidate_id": "candidate_h001_decoy",
      "expected_top_candidate_id": "candidate_h001",
      "expect_match": false,
      "defect": "BAD_CANDIDATE_RANKING"
    },
    {
      "metric": "occurred_at_within_tolerance",
      "actual_value": "2026-08-24T19:47:00+09:00",
      "expected_value": "2026-08-24T18:05:12+09:00",
      "max_deviation_sec": 2,
      "expect_match": false,
      "defect": "LARGE_TIMESTAMP_DEVIATION"
    },
    {
      "metric": "abstention_correctness",
      "actual_abstained": false,
      "expected_should_abstain": true,
      "expect_match": false,
      "defect": "FALSE_POSITIVE_NO_ABSTAIN"
    }
  ],
  "expected_metric_results": {
    "plate_exact_match_rate": 0.0,
    "candidate_top1_accuracy": 0.0,
    "time_within_tolerance_rate": 0.0,
    "abstention_correctness_rate": 0.0
  }
}
```
