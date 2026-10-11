# Customer identity across systems

One person appears in the bank's data under three keys, one per system. PINFL is the bridge; `datamart.clients_id_xref` is the hub that resolves them. Most of these columns are personal data.

## One person, three keys

| System | Warehouse table (source) | Key | Link to the person |
| --- | --- | --- | --- |
| Mobile app backend | `ods__mobile.app_user` (`users.app_user`) | `user_id` (UUID) | `pinfl`; `core_customer_id` = the iABS `customer_id` once onboarding KYC succeeds. One person may own several accounts |
| iABS core banking | `ods__iabs.customer` + `ods__iabs.customer_individual` (`core.*`) | `customer_id`; `customer_code` (8 digits, positions 10–17 of every account number) | `customer_individual.pinfl`, 1:1 on `customer_code` |
| TranzAxis credit and cards | `ods__tranzaxis.client` (`tx.client`) | `client_id` | `pinfl`; `core_customer_code` = the iABS `customer_code`. Contracts and cards hang off `client_id` |

**PINFL**, the 14-digit personal identification number of an individual, is the same in all three systems.

## The hub: `datamart.clients_id_xref`

One row per person known to any of the three systems: the union of their PINFLs, so app users who never became customers are included. Full reload every operating day.

| Column                                                         | Meaning                                            |
| -------------------------------------------------------------- | -------------------------------------------------- |
| `pinfl`                                                        | the key; unique and never empty                    |
| `iabs_customer_id`, `iabs_customer_code`                       | the iABS customer; empty if not (yet) a customer   |
| `tranzaxis_client_id`                                          | the TranzAxis client; empty without a card or loan |
| `primary_app_user_id`                                          | the newest app account, the one in use             |
| `app_user_ids`, `app_user_count`, `has_duplicate_app_accounts` | all app accounts, oldest first                     |
| `last_name`, `first_name`, `middle_name`, `birth_date`         | from iABS, else from the newest app account        |

Typical joins:

- loan, class, days past due → person: `datamart.contract_classification_daily.client_id` = `datamart.clients_id_xref.tranzaxis_client_id`;
- app activity → person: `user_id` → `ods__mobile.app_user.pinfl` (events of duplicate accounts belong to the same person);
- PINFL with overdue status, ready-made: `datamart.portfolio_daily` gives `pinfl`, `worst_classification`, `max_days_past_due` and `is_npl` per borrower and day.

## Counting people

- Count people by `pinfl`, never by `user_id`: app accounts sharing a PINFL are a known data-quality issue of the mobile backend.
- `datamart.kyc_funnel_daily.registrations` counts app accounts created on the day, duplicates included, not new people.
- Joining `ods__mobile.app_user` on PINFL fans out for people with duplicates; join through `datamart.clients_id_xref` instead.

```sql
select count(*) as people, sum(app_user_count) as app_accounts
from datamart.clients_id_xref
where app_user_count > 0;
```

## Personal data

These columns are personal data and carry the tag `PII.Sensitive` in the catalog wherever they appear: source system, `ext__`, ODS and marts.

| Table | Columns |
| --- | --- |
| `ods__mobile.app_user` | `phone_number`, `email`, `first_name`, `last_name`, `middle_name`, `date_of_birth`, `pinfl` |
| `ods__mobile.login_event`, `ods__mobile.device`, `ods__mobile.kyc_attempt` | `ip_address`; `device_fingerprint`; `face_photo_ref` (biometric selfie) |
| `ods__iabs.customer_individual` | `pinfl`, `last_name`, `first_name`, `middle_name`, `birth_date`, `passport_series`, `passport_number`, `passport_issued`, `address`, `phone`, `monthly_income` |
| `ods__iabs.customer`, `ods__iabs.customer_company`, `ods__iabs.payment_document` | `tax_id`; `director_name`, `director_pinfl`; `payer_name`, `payee_name` |
| `ods__tranzaxis.client`, `ods__tranzaxis.card` | `pinfl`, `full_name`, `birth_date`, `phone`; `pan_hash` |
| `datamart.clients_id_xref`, `datamart.portfolio_daily` | `pinfl`, names, `birth_date`; `pinfl` |

## Rules for using personal data

- **Need to know.** Access to marts goes through the role `l3__datamart__bs`, granted by Data Platform on request with the business reason. Select only the columns the purpose needs; prefer aggregates, or `tranzaxis_client_id` and `iabs_customer_code` over PINFL and names.
- **Data contract.** `datamart.clients_id_xref` carries a data contract whose terms of use (purpose limitation, minimisation, masking, incident reporting) apply to every extract made from it.
- **The law.** Processing follows the Law of the Republic of Uzbekistan "On Personal Data" (ZRU-547, 2019): a lawful basis, a defined purpose, protection against unauthorised access. Personal data of Uzbek citizens must be stored and processed inside Uzbekistan: keep extracts within the bank's perimeter, never on personal devices, e-mail or external services, AI tools included.
- **No PINFL in the open.** Keep PINFLs and names out of tickets, chats, file names and URLs.
