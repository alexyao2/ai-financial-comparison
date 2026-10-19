import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd

from simulation.engine import Portfolio, weights_from
from simulation.portfolio import simulate_quarter
from model_decisions.api import Budget, APIClient
from prompts.decision_validation import validate_decision
from run_experiment import fixed_decision, visible_events, run_strategy
from market_data.store import PriceStore, synthetic_prices
from model_decisions.investment import investment_config
from copy import deepcopy
from datetime import datetime


class SimulationTests(unittest.TestCase):
    def test_buy_sell_costs_and_conservation(self):
        p = Portfolio(cash=1000)
        p.rebalance({'SPY': 1}, .01)
        self.assertAlmostEqual(p.value, 1000/1.01)
        p.rebalance({'USD': 1}, .01)
        self.assertAlmostEqual(p.cash, (1000/1.01)*.99)
        self.assertAlmostEqual(p.value + p.fees, 1000)

    def test_switch_charges_both_legs(self):
        p = Portfolio(holdings={'SPY': 1000})
        p.rebalance({'TLT': 1}, .01)
        self.assertAlmostEqual(p.value, 1000*.99/1.01)
        self.assertAlmostEqual(p.value + p.fees, 1000)

    def test_deposit_does_not_rebalance_existing_holdings(self):
        p = Portfolio(cash=500, holdings={'SPY': 1000})
        p.invest_deposit(500, {'SPY': .5, 'USD': .5}, 0)
        self.assertEqual(p.holdings['SPY'], 1250)
        self.assertEqual(p.cash, 250)

    def test_cash_deposits_do_not_create_returns(self):
        p = Portfolio()
        for date in pd.date_range('2019-01-01', periods=3):
            row = p.step(date, {}, 500, {'USD':1}, .01, rebalance=True)
        self.assertEqual(row['portfolio_value'], 1500)
        self.assertEqual(row['time_weighted_return'], 0)
        self.assertEqual(row['drawdown'], 0)

    def test_legacy_sample_agrees(self):
        prices = pd.read_csv('data/prices/sample_prices.csv', index_col=0, parse_dates=True)
        d = fixed_decision('2019-01-01', [('individual_stock','AAPL',50),('broad_equity_etf','SPY',30),('treasury_bond_etf','TLT',20)], 'test')
        old = simulate_quarter(prices,d,10000,500,.01)
        p, month = Portfolio(), None
        for index,(date,row) in enumerate(prices.iterrows()):
            deposit = (10000 if index==0 else 0) + (500 if date.month != month else 0)
            result = p.step(date,row,deposit,weights_from(d),.01,rebalance=index==0)
            month=date.month
        self.assertAlmostEqual(result['portfolio_value'],old.iloc[-1].portfolio_value)
        self.assertAlmostEqual(result['portfolio_value'],13045.540408,places=5)
        self.assertEqual(result['total_contributed'],11500)

    def test_quarter_boundaries_do_not_reset_capital(self):
        config=deepcopy(investment_config)
        config['investment_start_date']=datetime(2019,1,1)
        config['investment_end_date']=datetime(2019,12,31)
        with tempfile.TemporaryDirectory() as folder:
            store=PriceStore('2019-01-01','2019-12-31',folder,synthetic_prices())
            calendar=store.get('SPY').loc['2019'].index
            frame,count=run_strategy('cash',config,store,calendar,Path(folder),{'USD':'cash'},[], 'test')
            self.assertEqual(count,4)
            self.assertEqual(frame.iloc[-1].portfolio_value,16000)
            self.assertEqual(frame.iloc[-1].total_fees,0)
            requests=sorted((Path(folder)/'cash/decisions').glob('*.request.json'))
            packet=json.loads(requests[1].read_text())['packet']
            self.assertLess(packet['decision_date'],packet['execution_date'])
            self.assertEqual(packet['portfolio']['total_contributed'],11500)
            for value in packet['market_information'].values():
                self.assertLessEqual(value['as_of'],packet['decision_date'])

    def test_future_events_hidden(self):
        events=[{'published_at':'2020-01-01','source':'test','description':'future'}]
        self.assertEqual(visible_events(events,pd.Timestamp('2019-12-31')),[])

    def test_invalid_weights_rejected(self):
        for weight in (True,float('nan'),float('inf'),101):
            d=fixed_decision('2019-01-01',[('cash','USD',weight)],'test')
            with self.assertRaises(ValueError): validate_decision(d)


class BudgetTests(unittest.TestCase):
    def test_rate_limit_can_be_retried_without_double_reservation(self):
        with tempfile.TemporaryDirectory() as folder:
            b = Budget(Path(folder)/'ledger.sqlite')
            b.reserve('one', 4)
            b.rate_limited('one')
            self.assertEqual(b.committed(), 0)
            b.reserve('one', 4)
            self.assertEqual(b.committed(), 4)

    def test_shared_cap_and_uncertain_requests(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'ledger.sqlite'
            b=Budget(path)
            b.reserve('one',4)
            with self.assertRaises(RuntimeError): Budget(path).reserve('two',2)
            with self.assertRaises(RuntimeError): b.reserve('one',0)
            b.settle('one',1)
            b.reserve('two',2)
            self.assertEqual(b.committed(),3)

    def test_api_cached_once_without_network(self):
        decision=fixed_decision('2019-01-01',[('cash','USD',100)],'test')
        raw={'model':'test','choices':[{'message':{'content':json.dumps(decision)}}],
             'usage':{'prompt_tokens':100,'completion_tokens':50}}
        from io import BytesIO
        settings={'provider':'groq','model':'test','key':'fake','input':1.,'output':2.}
        with tempfile.TemporaryDirectory() as folder, patch('model_decisions.api.provider_settings',return_value=settings), patch('urllib.request.urlopen',return_value=BytesIO(json.dumps(raw).encode())) as request:
            c=APIClient('groq',folder)
            self.assertEqual(c.decide('test',{}),decision)
            self.assertEqual(c.decide('test',{}),decision)
            self.assertEqual(request.call_count,1)
            self.assertTrue(c.last_metadata['cache_hit'])
            self.assertAlmostEqual(c.budget.committed(),.0002)

    def test_failed_api_retains_reservation(self):
        settings={'provider':'groq','model':'test','key':'fake','input':1.,'output':2.}
        with tempfile.TemporaryDirectory() as folder, patch('model_decisions.api.provider_settings',return_value=settings), patch('urllib.request.urlopen',side_effect=TimeoutError):
            c=APIClient('groq',folder)
            with self.assertRaises(TimeoutError): c.decide('test',{})
            self.assertGreater(c.budget.committed(),0)
            with self.assertRaises(RuntimeError): c.decide('test',{})


if __name__ == '__main__':
    unittest.main()
