## (O)wned Politicians

Compromised political elites are a problem. To assess how common it is, we check how many public breaches politicians are part of. We query the publicly listed emails of Lok Sabha members (MPs) against the HIBP database. We find that 31\% of the politicans in a Lok Sabha session have been part of at least one breach. More alarmingly, over 22\% of the politicians have had their sensitive data, e.g., Bank account numbers, Biometric data, Browsing histories, Chat logs, Credit card CVV, Credit cards, etc., breached. Given that only a small sliver of breaches become public, this should be treated as an extreme lower bound.

### Data and Scripts

* Politician Email Data
	* [EveryPolitician](data/everypol/)
		* [Get All EveryPol.](scripts/01_everypol_walkthrough.ipynb)
		* [Download CSVs](scripts/02_everypol_download_csvs.ipynb)
	* [Danish Parliament (2025)](data/)
	* [Norwegian Parliament (2025)](data/)
	* [Indian Parliament (1999--2025)](data/)
	* [Indian State Legislatures (2025)]
		* [Bihar](data/india/bihar/)
		* [UP](data/india/up/)
		* [Himachal Pradesh](data/india)
		* [Tamil Nadu](data/india/tn)
		* [Delhi](data/india/)
* [Get HIBP Data](scripts/03_download_hibp_everypol_india_eur_breaches.ipynb)
* [Combine and Analyze](scripts/04_hibp_everypol_ind_eur_combine.ipynb)

### Authors

Lucas Shen and Gaurav Sood