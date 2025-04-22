## How Often is Politicians’ Data Breached? Evidence from HIBP

Data breaches involving politicians are concerning because of the threat of impersonation and blackmail, among other nefarious things. To shed light on the concern, we estimate how frequently politicians' data is compromised. Using a dataset of 12,384 emails of politicians from 59 countries spanning three decades, we check whether these emails are part of breaches by using *Have I Been Pwned*, a widely used online service for searching public breach data. A third of the politicians have had their data breached at least once. More alarmingly, over one in five have had their sensitive data, such as bank account numbers, biometric data, browsing history, chat logs, credit card CVV, etc., breached. These numbers are still too optimistic for several reasons, including the fact that we do not have all the email addresses used by politicians. Accounting for some of the biases suggests that more than half the politicians have suffered a serious breach. In all, the data suggest urgent action is needed to protect politicians against cybersecurity threats.
### Data and Scripts

* Politician Email Data
	* [EveryPolitician](data/everypol/)
		* [Get All EveryPol.](scripts/01_everypol_walkthrough.ipynb)
		* [Download CSVs](scripts/02_everypol_download_csvs.ipynb)
	* [Danish Parliament (2025)](data/dk/)
	* [Norwegian Parliament (2025)](data/no/)
  	* [Greek Parliament](data/gr)
  	* [Argentinian Parliament](data/ar/)
  	* [Brazilian Parliament](data/ng/)
  	* [Nigerian Parliament](data/sg)
  	* [Singaporean Parliament](data/br/)
	* [Indian Parliament (1999--2025)](data/india/)
	* Indian State Legislatures (2025)
		* [Bihar](data/india/bihar/)
		* [UP](data/india/up/)
		* [Himachal Pradesh](data/india/)
		* [Tamil Nadu](data/india/tn/)
		* [Delhi](data/india/delhi/)
* [Get HIBP Data](scripts/03_download_hibp_everypol_india_eur_breaches.ipynb)
* [Combine and Analyze](scripts/04_hibp_everypol_ind_eur_combine.ipynb)

### Authors

Lucas Shen and Gaurav Sood

## 🔗 Adjacent Repositories

- [themains/reg_breach](https://github.com/themains/reg_breach) — Have I Been Pwned? Yes. Evidence from HIBP and Emails From Voter Registration Files.
- [themains/private_gov](https://github.com/themains/private_gov) — How common are third-party cookies, trackers, key loggers, etc. on government websites?
- [themains/pwned](https://github.com/themains/pwned) — How Often Are Americans' Accounts Breached?
- [themains/private_blacklight](https://github.com/themains/private_blacklight) — Privacy Online and Digital Divide on Online Privacy
- [themains/domain_knowledge](https://github.com/themains/domain_knowledge) — Domain Knowledge: Learning with pydomains
