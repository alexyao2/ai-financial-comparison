import json
from io import BytesIO
import urllib.error
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd

from simulation.engine import Portfolio, weights_from
from simulation.portfolio import simulate_quarter
from model_decisions.api import APIClient
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
            reports = sorted((Path(folder)/'cash/periods').glob('*.json'))
            self.assertEqual(len(reports), 4)
            first, second = [json.loads(p.read_text()) for p in reports[:2]]
            self.assertEqual(first['contributions'], 11500)
            self.assertEqual(second['contributions'], 1500)
            self.assertEqual(second['opening_portfolio']['portfolio_value'], 11500)
            self.assertEqual(second['net_gain'], 0)
            self.assertEqual(second['time_weighted_return'], 0)
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

    def test_completed_period_survives_next_review_failure(self):
        config = deepcopy(investment_config)
        config.update(investment_start_date=datetime(2019, 1, 1),
                      investment_end_date=datetime(2019, 6, 30))
        class FailingClient:
            last_metadata = {}

            def decide(self, system, packet):
                if packet['previous_decisions']:
                    raise TimeoutError('second review failed')
                return fixed_decision(packet['decision_date'], [('cash', 'USD', 100)], 'test')

        with tempfile.TemporaryDirectory() as folder:
            store = PriceStore('2019-01-01', '2019-06-30', folder, synthetic_prices())
            calendar = store.get('SPY').loc['2019-01-01':'2019-06-30'].index
            with self.assertRaises(TimeoutError):
                run_strategy('test', config, store, calendar, Path(folder),
                             {'USD': 'cash'}, [], 'test', FailingClient())
            reports = list((Path(folder)/'test/periods').glob('*.json'))
            self.assertEqual(len(reports), 1)
            report = json.loads(reports[0].read_text())
            self.assertEqual(report['end_date'], '2019-03-29')
            self.assertEqual(report['closing_portfolio']['portfolio_value'], 11500)

    def test_invalid_weights_rejected(self):
        for weight in (True,float('nan'),float('inf'),101):
            d=fixed_decision('2019-01-01',[('cash','USD',weight)],'test')
            with self.assertRaises(ValueError): validate_decision(d)


class APITests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        settings = patch('model_decisions.api.provider_settings', return_value={
            'provider': 'groq', 'model': 'test', 'key': 'fake-secret'})
        settings.start()
        self.addCleanup(settings.stop)
        sleep = patch('model_decisions.api.time.sleep')
        self.sleep = sleep.start()
        self.addCleanup(sleep.stop)

    def response(self, content='{"ok": true}'):
        return BytesIO(json.dumps({'choices': [{'message': {'content': content}}],
                                 'usage': {'prompt_tokens': 100, 'completion_tokens': 50}}).encode())

    def test_api_cached_once_with_usage(self):
        with patch('urllib.request.urlopen', return_value=self.response()) as request:
            client = APIClient('groq', self.root)
            for _ in range(2):
                self.assertEqual(client.decide('test', {}), {'ok': True})
            self.assertEqual(request.call_count, 1)
            self.assertEqual(request.call_args.args[0].get_header('User-agent'),
                             'ai-financial-comparison/1.0')
            self.assertTrue(request.call_args.kwargs['context'].check_hostname)
            self.assertTrue(client.last_metadata['cache_hit'])
            self.assertEqual(client.last_metadata['usage']['completion_tokens'], 50)
            self.assertNotIn('cost_usd', client.last_metadata)

    def test_groq_schema_preserves_existing_cache(self):
        with patch('urllib.request.urlopen', side_effect=[self.response(), self.response()]) as request:
            client = APIClient('groq', self.root)
            client.decide('test', {})
            original = next(client.cache.glob('*.json'))
            saved = original.read_bytes()
            client.settings['model'] = 'openai/gpt-oss-120b'
            client.decide('test', {})
            body = json.loads(request.call_args.args[0].data)
            fmt = body['response_format']
            self.assertEqual(fmt['type'], 'json_schema')
            self.assertTrue(fmt['json_schema']['strict'])
            self.assertIn('risks', fmt['json_schema']['schema']['required'])
            self.assertFalse(fmt['json_schema']['schema']['additionalProperties'])
            self.assertEqual(original.read_bytes(), saved)
            client.decide('test', {})
            self.assertEqual(request.call_count, 2)

    def test_temporary_error_retries_then_succeeds(self):
        error = urllib.error.HTTPError('https://example.test', 503, 'Unavailable', {}, BytesIO(b'busy'))
        with patch('urllib.request.urlopen', side_effect=[error, self.response()]) as request:
            client = APIClient('groq', self.root)
            self.assertEqual(client.decide('test', {}), {'ok': True})
            self.assertEqual(request.call_count, 2)
            self.assertEqual(client.last_metadata['attempts'], 2)
            self.sleep.assert_called_once_with(5)
        self.assertEqual(len(list((self.root / '.cache/errors').glob('*.json'))), 1)

    def test_access_error_not_retried_and_key_redacted(self):
        error = urllib.error.HTTPError('https://example.test', 403, 'Forbidden', {}, BytesIO(b'blocked fake-secret'))
        with patch('urllib.request.urlopen', side_effect=error) as request:
            with self.assertRaisesRegex(RuntimeError, 'HTTP 403'):
                APIClient('groq', self.root).decide('test', {})
            self.assertEqual(request.call_count, 1)
            self.sleep.assert_not_called()
        saved = next((self.root / '.cache/errors').glob('*.json')).read_text()
        self.assertNotIn('fake-secret', saved)

    def test_timeout_attempts_are_bounded_and_preserved(self):
        with patch('urllib.request.urlopen', side_effect=TimeoutError) as request:
            with self.assertRaises(TimeoutError):
                APIClient('groq', self.root).decide('test', {})
            self.assertEqual(request.call_count, 3)
            self.assertEqual([c.args[0] for c in self.sleep.call_args_list], [5, 10])
        self.assertEqual(len(list((self.root / '.cache/errors').glob('*.json'))), 3)

    def test_invalid_json_is_cached_not_retried(self):
        with patch('urllib.request.urlopen', return_value=self.response('not json')) as request:
            client = APIClient('groq', self.root)
            for _ in range(2):
                with self.assertRaises(ValueError): client.decide('test', {})
            self.assertEqual(request.call_count, 1)
            self.sleep.assert_not_called()


if __name__ == '__main__':
    unittest.main()
