from sadquant.models import MarketSnapshot
from sadquant.signals import score_snapshot


def snapshot(**overrides):
    data = {
        "ticker": "TEST",
        "last_price": 120.0,
        "change_20d_pct": 8.0,
        "change_60d_pct": 12.0,
        "rsi_14": 62.0,
        "sma_20": 115.0,
        "sma_50": 105.0,
        "sma_200": 90.0,
        "volatility_20d": 25.0,
        "high_52w": 125.0,
        "low_52w": 60.0,
        "observations": 252,
    }
    data.update(overrides)
    return MarketSnapshot(**data)


def test_long_bias_when_trend_and_momentum_are_positive():
    signal = score_snapshot(snapshot())
    assert signal.label == "LONG_BIAS"
    assert signal.score > 0


def test_short_bias_when_trend_and_momentum_are_negative():
    signal = score_snapshot(
        snapshot(
            last_price=80.0,
            sma_20=90.0,
            sma_50=100.0,
            sma_200=110.0,
            change_20d_pct=-8.0,
        )
    )
    assert signal.label == "SHORT_BIAS"
    assert signal.score < 0
