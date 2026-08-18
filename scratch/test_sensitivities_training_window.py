"""Check ADX and MA sensitivities for TrendPullbackATRTrailing on 2015-2020 Training Window."""

import sys
sys.path.insert(0, ".")

from core.backtest.engine import TransactionCostModel
from core.portfolio.engine import MultiAssetPortfolioEngine
from core.portfolio.universe import PointInTimeUniverseProvider
from scratch.test_reentry_training_window import TrendPullbackATRTrailingStrategy


def main() -> None:
    train_start = "2015-01-01"
    train_end = "2020-12-31"
    initial_capital = 1_000_000.0

    pit_provider = PointInTimeUniverseProvider(strict_mode=False)
    pit_provider.load_from_json("data/pit_universe_production_v5.json")
    tickers = sorted(list(pit_provider.get_constituents("NIFTY_50", "2018-01-01")))

    tests = [
        # (name, fast, slow, pb, adx_th, atr_m, r_tr, pos)
        ("ADX=15, ATR=3.0, r=0.02", 50, 200, 20, 15.0, 3.0, 0.02, 10),
        ("ADX=20, ATR=3.0, r=0.02", 50, 200, 20, 20.0, 3.0, 0.02, 10),
        ("ADX=25, ATR=3.0, r=0.02", 50, 200, 20, 25.0, 3.0, 0.02, 10),
        ("Fast=40, Slow=200, ADX=20, ATR=3.0", 40, 200, 20, 20.0, 3.0, 0.02, 10),
        ("Fast=50, Slow=200, ADX=20, ATR=3.0", 50, 200, 20, 20.0, 3.0, 0.02, 10),
        ("Fast=60, Slow=200, ADX=20, ATR=3.0", 60, 200, 20, 20.0, 3.0, 0.02, 10),
        ("Fast=50, Slow=200, PB=15, ADX=20", 50, 200, 15, 20.0, 3.0, 0.02, 10),
        ("Fast=50, Slow=200, PB=20, ADX=20", 50, 200, 20, 20.0, 3.0, 0.02, 10),
        ("Fast=50, Slow=200, PB=25, ADX=20", 50, 200, 25, 20.0, 3.0, 0.02, 10),
    ]

    print(f"{'Sensitivity Test':<40} | {'Return':<8} | {'Max DD':<8} | {'Sharpe':<7} | {'WinRate':<8} | {'Trades'}")
    print("-" * 86)

    for name, f, s, pb, adx_th, atr_m, r_tr, pos in tests:
        strat = TrendPullbackATRTrailingStrategy(
            fast_period=f, slow_period=s, pullback_period=pb,
            min_adx_threshold=adx_th, atr_multiplier=atr_m,
            enable_pullback_reentry=True
        )
        eng = MultiAssetPortfolioEngine(
            fixture_dir="fixtures/yfinance_historical",
            cost_model=TransactionCostModel(),
            pit_provider=pit_provider,
            index_symbol="NIFTY_50",
            strict_pit=False
        )
        res = eng.run_portfolio_backtest(
            strategy=strat,
            tickers=tickers,
            start_date=train_start,
            end_date=train_end,
            initial_capital=initial_capital,
            risk_per_trade=r_tr,
            max_positions=pos
        )
        print(f"{name:<40} | {res.total_return*100:>7.2f}% | {res.metrics.max_drawdown*100:>7.2f}% | {res.metrics.sharpe_ratio:>7.2f} | {res.metrics.win_rate*100:>7.2f}% | {len(res.trades):>6}")


if __name__ == "__main__":
    main()
