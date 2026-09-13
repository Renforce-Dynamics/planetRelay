import pytest

from planetrelay.config import load_config
from planetrelay.latency import LatencyResult, HEADER, MAGIC, make_packet, percentile



def test_latency_packet_has_requested_size_and_header():
    packet = make_packet(42, 123456789, 108)
    assert len(packet) == 108
    assert HEADER.unpack_from(packet) == (MAGIC, 42, 123456789)


def test_latency_packet_rejects_too_small_size():
    with pytest.raises(ValueError, match="at least"):
        make_packet(0, 0, HEADER.size - 1)


def test_latency_summary_reports_loss_and_percentiles():
    result = LatencyResult(
        sent=5,
        received=4,
        lost=1,
        invalid=2,
        duplicates=1,
        rtt_ms=(4.0, 1.0, 3.0, 2.0),
    )
    summary = result.summary()
    assert summary["loss_percent"] == 20.0
    assert summary["rtt_min_ms"] == 1.0
    assert summary["rtt_p50_ms"] == 2.5
    assert summary["rtt_max_ms"] == 4.0
    assert percentile((1.0, 2.0, 3.0), 95) == pytest.approx(2.9)


