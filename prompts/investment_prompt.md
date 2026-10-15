Investment Objective: Using the supplied household financial report and investment configuration, select investments from the five permitted investment categories and assign portfolio weights to maximize the simulated portfolio’s ending value between the specified start and end dates. Allocations must remain within the available balance, total 100% including cash, and use no borrowing, short selling, or leverage. Selected investments must have been available on the simulated decision date.   

The assets are defined as follows:
individual_stock: Shares representing ownership in a publicly traded company.
broad_equity_etf: An exchange-traded fund tracking a diversified stock-market index, such as the S&P 500 or a total-market index.
treasury_bond_etf: An exchange-traded fund holding U.S. Treasury securities, including bills, notes, or bonds.
cryptocurrency: Direct ownership of a cryptocurrency, valued in U.S. dollars using a specified market-data source.
cash: Uninvested U.S. dollars held in the simulated account, earning 0% interest for this experiment.

Contributions: The configured contribution is deposited monthly, independently of the decision schedule. Between reviews, new contributions are allocated using the most recently selected target weights.
Trading Costs: Use the transaction-cost assumptions supplied in the investment configuration. The simulator calculates and deducts these costs.
Cash: Earns 0% interest.
Fractional holdings: Fractional shares and cryptocurrency units are allowed.


Decision frequency: Make an initial portfolio allocation, then review it at the frequency specified in the investment configuration.
Decision inputs: At each review, you will receive the household financial report, current holdings, cash balance, portfolio value, previous decisions, and an updated market-information packet.
Your task: Use the supplied information to retain or revise your investments and target weights. Explain the factors driving your decision and the trade-offs you accept. Your allocation must satisfy all investment constraints.
Permitted decisions: You may retain your allocations, change weights, add eligible investments, remove investments, or hold cash. All decisions must satisfy the investment constraints.
Execution: The simulator trades toward the newly selected weights at the next eligible execution time after the information cutoff. You cannot receive returns from a period before your decision takes effect.

Return one valid JSON object, without Markdown fences or surrounding commentary. Include decision_date, allocations, rationale, and risks. Each entry in allocations must contain category, identifier, and weight. These allocations describe the complete target portfolio after execution, not the current holdings or individual trades. Weights are percentages between 0 and 100 and must total 100. An existing holding omitted from the response has a target weight of zero. Represent cash with category cash and identifier USD.


decision_date:	Identifies the review, decision_date must use YYYY-MM-DD and match the supplied review date.
allocations:	Complete target portfolio, including any cash.
Category, instrument identifier, weight:	Identifies each holding and its allocation.
rationale:	Explains the main factors and trade-offs, should be an array of strings.
risks:	Records what could undermine the decision, should be an array of strings.