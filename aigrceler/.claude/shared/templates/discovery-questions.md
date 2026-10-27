# Discovery questions (ask in plain words)

Generated from `shared/catalog/discovery-profile.json`; do not edit by hand. The engine tracks the answers (`aig profile show`), asks them in batches by person (`aig profile plan`), and shows them as `00-status/discovery-record.md`.

Depth follows the lane: core questions for every system (22), plus standard (31), plus full (24). Questions marked **critical** decide the tier, the lane or a risk floor and cannot be recorded as not known. Of the questions that apply to a system, no more than 20 percent may be unknown or skipped.

Record each answer with its source: `aig profile set --field <id> --value "..." --source "<who or which document>"`.

## A. Purpose and ownership

- **purpose**: In one or two sentences, what does the system do, and who asked for it?
  - asks: the business owner; depth: all systems. Why: Every later judgment (risk, controls, legal duties) is made against this purpose.
- **business_owner**: Who is the one person who answers for what this system does to customers and the business?
  - asks: AI Governance; depth: all systems. Why: Without a named owner nobody can be asked to fix a problem or accept a risk.
- **related_ai_use**: Does anyone working on this process use other AI tools that are not on the company's list (free chatbots, browser add-ins, AI features inside software you already pay for)? Which ones, and what goes into them?
  - asks: the business owner; depth: all systems. Why: Unlisted AI tools beside this system can leak data or change results without anyone governing them.
- **lifecycle_stage**: Where is it today: still an idea, a pilot, in everyday use, or being retired?
  - asks: the business owner; depth: standard and full lanes. Why: A system already in use needs its controls sooner than one still being planned.
  - Answer is one of: idea, pilot, in-use, being-retired.
- **technical_owner**: Who looks after it technically from day to day (the person to call when it breaks)?
  - asks: the business owner; depth: standard and full lanes. Why: Incidents and changes need a technical person who can act.
- **intended_use**: What specific uses is it meant for, and what must it never be used for?
  - asks: the business owner; depth: standard and full lanes. Why: Use outside the intended purpose is a main source of harm and of legal exposure.
- **in_use_since**: If it is already in use, since when, and how many people have used it so far?
  - asks: the business owner; depth: full lane only. Why: Time in use shows how much history (results, complaints) exists to learn from.
- **business_value**: What problem does it solve, and what happens to the business if it is switched off?
  - asks: the business owner; depth: full lane only. Why: How much the business depends on it sets how hard it is to stop it when something goes wrong.

## B. People who use it and people it affects

- **users** (critical): Who uses it (which roles or customers), and roughly how many people?
  - asks: the business owner; depth: all systems. Why: Who uses it decides what training and oversight they need.
- **user_scale** (critical): How many people use it or are affected by it? few = a handful, many = hundreds, very-many = thousands or more.
  - asks: the business owner; depth: all systems. Why: Scale sets the tier: more people means a mistake costs more.
  - Answer is one of: few, many, very-many.
- **affected_people** (critical): Who is affected by what it produces, even if they never see it (customers, job applicants, patients, staff, the public)?
  - asks: the business owner; depth: all systems. Why: The people affected are who the risk assessment is really about.
- **vulnerable_groups**: Are children, patients, job seekers, employees, elderly people or people in financial difficulty among those affected? Say which, or say none.
  - asks: the business owner; depth: standard and full lanes. Why: Groups with less power or protection are harmed more easily and are protected more strongly by law.
- **user_training**: What training do the people who use or review the system have?
  - asks: operations; depth: full lane only. Why: People who do not know its limits trust it too much or too little.
- **affected_consulted**: Have the people it affects, or their representatives, been asked for their views? How, and what changed because of it?
  - asks: the business owner; depth: full lane only. Why: Hearing from affected people finds harms the builders cannot see.
- **societal_effect**: Could it affect groups beyond its direct users (a community, a profession, the environment)?
  - asks: the business owner; depth: full lane only. Why: Wider effects need to be named before they can be weighed.

## C. Decisions and human control

- **about_people** (critical): Does it decide, rank, score or recommend anything about an identifiable person (hiring, credit, care, pricing, access, discipline)? Answer yes or no, and say what.
  - asks: the business owner; depth: all systems. Why: Decisions about people carry the strongest fairness and legal duties and rule out the light lane.
- **decisions_made**: What exactly does it decide or recommend, and what happens next because of its output?
  - asks: the business owner; depth: standard and full lanes. Why: The step after the output shows how much damage a wrong output can do.
- **autonomy** (critical): Is every output checked by a person before it is used (reviewed), only some outputs (sampled), or none (automated)?
  - asks: the business owner; depth: all systems. Why: The less a person checks, the more the system itself must be trusted.
  - Answer is one of: reviewed, sampled, automated.
- **human_review** (critical): Can a person overrule it? Who, how, and how often do they actually do so?
  - asks: the business owner; depth: all systems. Why: A review step that nobody uses to change anything is not oversight.
- **consequential_actions** (critical): Can it take actions with real effects on its own (send messages, change records, spend money, call other systems)? Answer yes or no, and say what.
  - asks: engineering or data science; depth: all systems. Why: A system that acts, and not only advises, can cause harm at machine speed.
- **customer_output** (critical): Does it write or send anything to customers or the public without a person checking it first? Answer yes or no.
  - asks: the business owner; depth: all systems. Why: Unchecked output reaching the public is a reputational and legal risk and rules out the light lane.
- **ai_disclosure**: Are people told that they are dealing with AI, or that AI is used on their information? How?
  - asks: the business owner; depth: standard and full lanes. Why: People have a right to know, and surprise damages trust.
- **appeal_path**: How can an affected person question a result, ask for a person to look again, or report a problem?
  - asks: the business owner; depth: standard and full lanes. Why: Without a way to contest a result, errors about people stay uncorrected.
  - Asked only when it helps decide things about people or it sends output to customers without review or it uses personal data.

## D. Data

- **data_sources** (critical): What data does it use (records, documents, prompts, files), and where does each kind come from?
  - asks: engineering or data science; depth: all systems. Why: Poor or unknown data is the most common cause of poor results.
- **data_kind** (critical): Is any of the data about identifiable people (personal), or about health, beliefs, biometrics, ethnicity, children, finances or criminal records (sensitive)? none, personal or sensitive.
  - asks: engineering or data science; depth: all systems. Why: Personal and sensitive data bring privacy duties and rule out the light lane.
  - Answer is one of: none, personal, sensitive.
- **data_origin**: Who owns the data, and are you allowed to use it for this? Is it your own records, customer-provided, bought, scraped, public or supplied by a vendor?
  - asks: engineering or data science; depth: standard and full lanes. Why: Data used without the right to use it taints everything built on it.
- **data_basis**: What permission or reason does the company rely on to use personal data this way (consent, contract, legitimate interest), and were people told? Has counsel or your privacy officer confirmed it?
  - asks: legal-compliance; depth: standard and full lanes. Why: A system built on personal data without a valid basis can be ordered to stop. This is a question for counsel, not for AIGRCeler to answer.
  - Asked only when it uses personal data or it uses sensitive data.
- **data_retention**: How long is the personal data kept, and can it be deleted when someone asks?
  - asks: engineering or data science; depth: standard and full lanes. Why: Keeping data too long or being unable to delete it is a common finding.
  - Asked only when it uses personal data or it uses sensitive data.
- **data_flows_out**: What company data leaves the company (to the vendor and its sub-suppliers), and to which countries?
  - asks: engineering or data science; depth: standard and full lanes. Why: Data sent outside is out of your control and may cross borders.
  - Asked only when the sourcing mode is adapted-from-third-party-base or third-party-service or self-hosted-open-source or embedded-in-vendor-product; or when it uses personal data or it uses sensitive data.
- **data_quality**: How is the quality of the data checked, and is it checked that it fits the people the system affects?
  - asks: engineering or data science; depth: full lane only. Why: Data that does not represent the people affected produces unfair results.
- **prompts_logs**: Do prompts, logs or outputs contain personal or confidential information? Who can read them?
  - asks: security; depth: full lane only. Why: Logs and prompts are a quiet place for data to leak.
  - Asked only when it generates text, images or other content or it uses personal data.
- **training_data**: Was it trained or fine-tuned on company data? Is training data kept apart from test data and recorded for each version?
  - asks: engineering or data science; depth: full lane only. Why: You cannot explain or repeat a result without knowing what the model learned from.
  - Asked only when the sourcing mode is built-in-house or adapted-from-third-party-base or self-hosted-open-source.

## E. Model and technology

- **sourcing_mode** (critical): Did you build it, adapt someone else's model, buy a service, run an open-source model yourselves, or is it a feature inside a product you bought?
  - asks: engineering or data science; depth: all systems. Why: How it was sourced decides which risks and controls apply.
  - Answer is one of: built-in-house, adapted-from-third-party-base, third-party-service, self-hosted-open-source, embedded-in-vendor-product.
- **vendor_model**: Which vendor, and which model or product name?
  - asks: engineering or data science; depth: all systems. Why: You cannot check a vendor or follow its changes without knowing who it is.
  - Asked only when the sourcing mode is adapted-from-third-party-base or third-party-service or self-hosted-open-source or embedded-in-vendor-product.
- **model_version**: Which version is in use today, and how would you find out that it changed?
  - asks: engineering or data science; depth: standard and full lanes. Why: A silent version change can break behaviour, and proof tied to an old version stops counting.
- **generative**: Does it write text, images, code or speech (generative AI)? Answer yes or no.
  - asks: engineering or data science; depth: all systems. Why: Generative systems can invent facts, leak data and be tricked by their inputs.
- **technique**: What kind of AI is it (classifier, prediction, recommendation, language model, agent...)?
  - asks: engineering or data science; depth: full lane only. Why: The kind of AI decides how it fails and how it can be tested.
- **hosting**: Where does it run (vendor cloud, your cloud, your own servers, a device), and in which country?
  - asks: engineering or data science; depth: standard and full lanes. Why: Where it runs decides who can reach it and which country's rules touch the data.
- **integrations_tools**: Which tools, plug-ins or other systems can it call or read from, and with what permissions?
  - asks: engineering or data science; depth: standard and full lanes. Why: Every connection is a way for a failure or an attack to spread.
- **change_process**: How is it changed or updated, by whom, how often, and how is a change tested before it goes live?
  - asks: engineering or data science; depth: standard and full lanes. Why: Untested changes quietly break behaviour that was once checked.
- **gpai**: Is it built on a general-purpose AI model from a provider (a large language model)? Which one, and what documentation does the provider give you about it?
  - asks: engineering or data science; depth: full lane only. Why: Providers of general-purpose models owe their customers documentation; you need it to judge your own risk.
  - Asked only when the sourcing mode is adapted-from-third-party-base or third-party-service or self-hosted-open-source or embedded-in-vendor-product.
- **licences**: What licence or terms cover the model, the data and the outputs (including open-source and intellectual property)?
  - asks: legal-compliance; depth: full lane only. Why: Licence terms can limit use or make the company liable.
  - Asked only when the sourcing mode is not built-in-house.
- **resources**: What people, computing and budget does it take to run and oversee it? Who would take over if they left?
  - asks: operations; depth: full lane only. Why: A system nobody has time to oversee is unsupervised in practice.

## F. Testing and performance

- **eval_metrics** (critical): How does anyone check that it works well? What is measured, and who looks at the result?
  - asks: engineering or data science; depth: all systems. Why: If nobody measures it, nobody will notice when it gets worse.
- **known_limits**: What are its known weaknesses, where does it fail, and what should it never be trusted for?
  - asks: engineering or data science; depth: standard and full lanes. Why: Known limits must reach the people who rely on the system.
- **test_results**: What testing was done before it was used, and what were the results (accuracy, unusual inputs, fairness)?
  - asks: engineering or data science; depth: standard and full lanes. Why: Results before launch are the baseline for every later check.
- **bias_testing**: Was it checked for uneven results across groups (gender, age, ethnicity, language, disability)? What was found?
  - asks: engineering or data science; depth: standard and full lanes. Why: A system can be accurate on average and unfair to a group.
  - Asked only when it helps decide things about people or it uses personal data.
- **monitoring_now**: What is watched in live use (accuracy, drift, complaints, cost, errors), and who looks at it?
  - asks: operations; depth: standard and full lanes. Why: Results drift as the world changes; only watching shows it.
- **past_problems**: Have there been errors, complaints, near-misses or incidents with it? What happened and what was done?
  - asks: the business owner; depth: standard and full lanes. Why: Past problems are the best predictor of future ones.
- **target_level**: What level of accuracy or error is acceptable for this use, and who decided that?
  - asks: engineering or data science; depth: full lane only. Why: Without a stated target nobody can say whether it is good enough.
- **explainability**: Can someone explain, in plain words, why it gave a particular result?
  - asks: engineering or data science; depth: full lane only. Why: People affected by a decision are entitled to understand it.
  - Asked only when it helps decide things about people.
- **adversarial_testing**: Has anyone tried to trick, break or misuse it (red-teaming, prompt-injection tests, security testing)? What did they find?
  - asks: security; depth: full lane only. Why: Systems that have never been attacked on purpose have unknown weaknesses.

## G. Security and access

- **access_control**: Who can use it, change it or see inside it (including its data and keys)? How is that access reviewed?
  - asks: security; depth: standard and full lanes. Why: Uncontrolled access lets the wrong person change or steal it.
- **logging**: What records are kept of what it was asked and what it did, for how long, and who can read them?
  - asks: security; depth: standard and full lanes. Why: Without records you cannot show a regulator or a customer what happened.
- **secrets_keys**: Where are its passwords and service keys kept, and who can see them?
  - asks: security; depth: full lane only. Why: Leaked keys give attackers the same access the system has.
  - Asked only when the sourcing mode is adapted-from-third-party-base or third-party-service or self-hosted-open-source or embedded-in-vendor-product; or when it generates text, images or other content.
- **security_review**: Has the code, the libraries, the running system or the vendor been security-tested or assessed? When, and what was found?
  - asks: security; depth: full lane only. Why: Vulnerable software or a compromised component can undermine everything else.
- **misuse_paths**: How could someone misuse or attack it, and what stops them?
  - asks: security; depth: full lane only. Why: Naming the attack paths is the start of defending them.

## H. Dependencies and fallback

- **downstream_dependencies**: What other systems, reports or decisions depend on what it produces? (Say 'nothing' if nothing does.)
  - asks: operations; depth: all systems. Why: A failure spreads to everything that depends on it.
- **upstream_dependencies**: What does it depend on (data feeds, vendor services, other systems)?
  - asks: engineering or data science; depth: full lane only. Why: If an input fails or changes, the system's results change with it.
- **fallback**: If it is wrong or down, what happens? Is there a manual way to carry on, and how long can the business cope without it?
  - asks: operations; depth: standard and full lanes. Why: A system with no fallback cannot be switched off safely.

## I. Harm and impact

- **safety_impact** (critical): Could a wrong result hurt someone's health or physical safety? Answer yes or no.
  - asks: the business owner; depth: all systems. Why: Safety impact rules out the light lane and raises the minimum risk.
- **impact_level** (critical): If it is wrong, how bad is the worst realistic outcome? minor = an annoyance, business = money or reputation, rights-or-safety = someone's rights, livelihood, health or safety.
  - asks: the business owner; depth: all systems. Why: This is the main input to the tier.
  - Answer is one of: minor, business, rights-or-safety.
- **worst_case**: Describe the worst realistic thing that could happen if it is wrong, who would be hurt, and whether it could be undone.
  - asks: the business owner; depth: standard and full lanes. Why: A concrete worst case makes the likelihood and impact ratings honest.

## J. Legal and regulatory context

- **jurisdictions** (critical): In which countries or regions are the people it affects, and where does the company operate it?
  - asks: AI Governance; depth: all systems. Why: The countries decide which laws apply.
- **regulated_sector** (critical): Is it used in a regulated field (banking, insurance, health, employment, education, public services)? Answer yes or no, and say which.
  - asks: AI Governance; depth: all systems. Why: Regulated sectors have their own rules and rule out the light lane.
- **eu_nexus**: Does it affect people in the European Union, or is any of it run there? yes, no or not-sure.
  - asks: AI Governance; depth: standard and full lanes. Why: If it touches the EU, the EU AI Act may apply. Whether it does is a question for counsel.
  - Answer is one of: yes, no, not-sure.
- **eu_role**: Under the EU AI Act, is the company the one that built it and puts it on the market (provider), only uses it (deployer), imports it, resells it, or is it not sure? provider, deployer, importer, distributor, authorised-representative, none or not-sure.
  - asks: legal-compliance; depth: standard and full lanes. Why: The duties differ greatly by role. This is a question for counsel.
  - Asked only when the answer to "whether it touches the EU" is yes/not-sure.
  - Answer is one of: provider, deployer, importer, distributor, authorised-representative, none, not-sure.
- **eu_class_view**: What is the company's current view of how the EU AI Act classifies this use, and has counsel been asked? prohibited-concern, high-risk, transparency-duty, minimal or not-sure.
  - asks: legal-compliance; depth: standard and full lanes. Why: A prohibited or high-risk use needs legal steps before it can go live. This records a view; counsel decides.
  - Asked only when the answer to "whether it touches the EU" is yes/not-sure.
  - Answer is one of: prohibited-concern, high-risk, transparency-duty, minimal, not-sure.
- **counsel_asked**: Have legal counsel or your privacy officer been asked about this system? Which questions are still open with them?
  - asks: AI Governance; depth: standard and full lanes. Why: Legal questions only counsel can answer must not stay unasked.
- **prior_assessments**: Which impact or privacy assessments, audits or approvals already exist for it, and when were they done?
  - asks: legal-compliance; depth: standard and full lanes. Why: Existing assessments save work and show what has already been judged.
- **contracts**: Which contract or terms cover it (data processing, audit rights, security, liability, change notice)? Where are they?
  - asks: legal-compliance; depth: full lane only. Why: The contract decides who pays and who must act when something goes wrong.
  - Asked only when the sourcing mode is not built-in-house.
- **sector_rules**: Which sector rules or regulator guidance do you know apply to it?
  - asks: legal-compliance; depth: full lane only. Why: Sector duties are easy to miss and are enforced separately.
  - Asked only when it is used in a regulated sector.
- **certifications**: Which standards or certifications does the company or the vendor hold or work towards (ISO 42001, ISO 27001, SOC 2...)?
  - asks: AI Governance; depth: full lane only. Why: Certifications show what has been independently checked.

## K. Existing governance

- **oversight_owner**: Who reviews its results day to day, and how much of their time does that take?
  - asks: the business owner; depth: standard and full lanes. Why: A named reviewer with time is what makes oversight real.
- **incident_contact**: Who is called when it goes wrong, and who is the vendor's contact for an incident?
  - asks: operations; depth: standard and full lanes. Why: In an incident every minute lost to finding the right person counts.
- **existing_policies**: Which existing company policies already cover it (acceptable use, data, security, procurement)?
  - asks: AI Governance; depth: full lane only. Why: Existing policies are the base the AI controls build on.
- **approval_history**: Who approved it for use, when, and on what basis?
  - asks: AI Governance; depth: full lane only. Why: A launch without a recorded approval cannot be defended afterwards.

## Documents to collect

Note each with `aig profile doc --kind <kind> --name "..." --status <status> --source "..."`.

- **vendor-contract**: Vendor contract and data processing terms (standard and full lanes)
- **vendor-docs**: Vendor model documentation and stated limits (standard and full lanes)
- **impact-assessment**: Privacy or impact assessment already done (standard and full lanes)
- **architecture**: Architecture or data-flow diagram (standard and full lanes)
- **test-reports**: Test and evaluation reports (standard and full lanes)
- **user-notice**: Notice or privacy statement shown to affected people (standard and full lanes)
- **policies**: Policies that already cover the system (full lane only)
- **incident-log**: Log of past errors, complaints and incidents (full lane only)
- **model-card**: Model card or technical documentation (full lane only)
