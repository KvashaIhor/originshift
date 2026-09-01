# Validation scorecard

Generated 2026-09-01 by `python -m originshift.validate --emit`.
Corpus `HTSUS-2026`, from eCFR issue `2026-08-26`.

Ground truth is CBP's own HQ rulings, which are binding determinations by
the authority whose rules this corpus compiles.

## Agreement — does the resolver reach CBP's conclusion?

- curated cases: **30**
- a definite call: **22/30**
- agreement with CBP: **22/22**
- cases stating both the materials' origins and the country CBP held,
  so the whole hierarchy can be scored: **8**, of which
  **8/8** reached CBP's country
- curated textile cases: **13**, of which **13/13**
  reached CBP's country and **13/13** by the same paragraph of (c)

## Rule fidelity — does the corpus hold the rule CBP applied?

### 19 CFR 102.20

- HQ rulings examined: **312**
- of those, quoting a 102.20 rule: **228**
- rule quotations scored: **242**

| Verdict | n |
|---|---|
| `equivalent` | 167 |
| `differs` | 40 |
| `target_absent` | 29 |
| `unparsed` | 6 |

**Coverage 85.5%** — quoted rules the corpus places at all.  
**Rule fidelity 70.8%** — placed rules it holds as CBP stated them.

By era of the ruling. The corpus answers under one nomenclature vintage, so
agreement with older rulings falls away, and does:

| Era of ruling | n | Coverage | Rule fidelity |
|---|---|---|---|
| 2020–2026 | 45 | 97.8% | 86.4% |
| 2003–2019 | 28 | 85.7% | 66.7% |
| 1994–2002 | 169 | 82.2% | 67.3% |

HS renumbering moves the codes out from under older rulings, which is why a
vintage is pinned at all.

### 19 CFR 102.21

- HQ rulings examined: **554**
- of those, quoting an (e)(1) rule: **94**
- rule quotations scored: **97**
- coverage **89.7%**, rule fidelity **67.4%**

## What is excluded before scoring, and why

Rulings citing 102.20 routinely also quote **USMCA and NAFTA preferential
rules**, which are worded almost identically and are a different legal test.
Those are excluded. A quotation is also cut where the rule ends, since one
running on into CBP's prose picks up codes that are not part of it.

Comparison is structural, because CBP quotes the regulation loosely: it
pluralises "heading", writes headings in the HS dotted form (`48.17` for
`4817`), and runs a quotation into its own prose.

## Every disagreement

Listed in full. They are not all corpus defects.

**558759** (1995) — `differs`

> A change to headings 48.17 through 48.22 from any other heading, including another heading within that group.

corpus holds (('4817-4822',), (('any_other', 'heading'),), ('4818', '9619')), CBP quoted (('4817-4822',), (('any_other', 'heading'),), ())

**558760** (1995) — `differs`

> A change to subheading 8471.92 through 8472.90 from any other subheading, except when resulting from a simple assembly.

corpus holds (('8471.60-8472.90',), (('any_other', 'subheading'),), ('8473', '8504.40')), CBP quoted (('8471.92-8472.90',), (('any_other', 'subheading'),), ())

**558891** (1995) — `differs`

> A change to subheading 9404.90 from any other heading.

corpus holds (('9404.30-9404.90',), (('any_other', 'heading'),), ()), CBP quoted (('9404.90',), (('any_other', 'heading'),), ())

**558955** (1995) — `differs`

> A change to heading 6801 through 6809 from any other heading, including another heading within that group.

corpus holds (('6801-6808',), (('any_other', 'heading'),), ()), CBP quoted (('6801-6809',), (('any_other', 'heading'),), ())

**558978** (1995) — `target_absent`

> A change to subheading 9504.10 through 9506.29 from any other subheading, including within that group.

no rule in the corpus targets 9504.10

**559186** (1995) — `differs`

> A change to subheadings 6406.20 through 6406.99 from any other chapter.

corpus holds (('6406.20-6406.90',), (('any_other', 'chapter'),), ()), CBP quoted (('6406.20-6406.99',), (('any_other', 'chapter'),), ())

**559198** (1995) — `target_absent`

> A change to heading 8523 from any other heading.

no rule in the corpus targets 8523

**559424** (1995) — `differs`

> A change to subheading 3003.90 from any other subheading, provided that the domestic content of the therapeutic or prophylactic component/s is no less than 40 percent by weight of the total therapeutic or prophylactic content.

corpus holds (('3003.60-3003.90',), (('any_other', 'subheading'),), ()), CBP quoted (('3003.90',), (('any_other', 'subheading'),), ())

**559424** (1995) — `differs`

> A change to subheading 3004.90 from any other subheading, except from subheading 3003.90, provided that the domestic content of the therapeutic or prophylactic component/s is no less than 40 percent by weight of the total therapeutic or prophylactic content.

corpus holds (('3004.60-3004.90',), (('any_other', 'subheading'),), ('3003.60-3003.90', '3006.92')), CBP quoted (('3004.90',), (('any_other', 'subheading'),), ('3003.90',))

**559451** (1996) — `differs`

> A change to subheading 1806.90 from any other subheading.

corpus holds (('1806.90',), (('any_other', 'subheading'),), ('1602.90',)), CBP quoted (('1806.90',), (('any_other', 'subheading'),), ())

**559811** (1996) — `differs`

> A change to headings 4817 through 4822 from any other heading, including another heading within that group.

corpus holds (('4817-4822',), (('any_other', 'heading'),), ('4818', '9619')), CBP quoted (('4817-4822',), (('any_other', 'heading'),), ())

**559829** (1997) — `target_absent`

> A change to subheading 3002.10 through 3002.90 from any other subheading, including another subheading within that group.

no rule in the corpus targets 3002.10

**560081** (1997) — `unparsed`

> A change to subheading 9615.11 through 9615.90, including another subheading within that group.

the quotation does not parse as a rule

**560140** (1997) — `differs`

> A change to heading 6801 through 6809 from any other heading, including another heading within that group.

corpus holds (('6801-6808',), (('any_other', 'heading'),), ()), CBP quoted (('6801-6809',), (('any_other', 'heading'),), ())

**560195** (1997) — `differs`

> A change to subheading 3809.91 through 3809.99 from any other subheading, including another subheading within that group.

corpus holds (('3809.91-3809.93',), (('any_other', 'subheading'),), ()), CBP quoted (('3809.91-3809.99',), (('any_other', 'subheading'),), ())

**560394** (1997) — `target_absent`

> A change to heading 3402.11 through 3402.20 from any other subheading, including another subheading within that group.

no rule in the corpus targets 3402.11

**560519** (1998) — `target_absent`

> A change to subheading 8525.10 through 8525.20 from any other subheading outside that group.

no rule in the corpus targets 8525.10

**560552** (1997) — `differs`

> a change to finished leather of heading 4104 through 4107 from wet blue hides or leather".

corpus holds (('4104-4106',), (('any_other', 'heading'),), ('4101-4103', '4107', '4112', '4113')), CBP quoted (('4104-4107',), (), ())

**560599** (1998) — `target_absent`

> A change to subheading 8525.10 through 8525.20 from any other subheading outside that group.

no rule in the corpus targets 8525.10

**560640** (1998) — `target_absent`

> A change to subheading 3808.10 from any other subheading, except from subheading 1302.14 or from any insecticide classified in Chapter 28 or 29.

no rule in the corpus targets 3808.10

**560667** (1998) — `target_absent`

> A change to subheading 8708.39 from any other heading.

no rule in the corpus targets 8708.39

**560667** (1998) — `differs`

> A change to subheading 8708.99 from any other subheading.

corpus holds (('8708.99',), (('any_other', 'subheading'),), ('8708.40', '8708.50', '8708.80', '8708.91', '8708.92', '8708.94', '8708.95')), CBP quoted (('8708.99',), (('any_other', 'subheading'),), ())

**560681** (1997) — `differs`

> A change to heading 3822 from any other heading, except from subheading 3002.10 or 3502.90 or heading 3504.

corpus holds (('3822',), (('any_other', 'heading'),), ('3002.12-3002.15', '3502.90', '3504', '3822.11-3822.12', '3822.19')), CBP quoted (('3822',), (('any_other', 'heading'),), ('3002.10', '3502.90', '3504'))

**560754** (1998) — `target_absent`

> A change to subheading 7419.10 through 7419.99 from any other subheading, including another subheading within that group.

no rule in the corpus targets 7419.10

**560936** (1999) — `differs`

> A change to subheading 8716.10 through 8716.80 from any other heading, except from subheading 8716.90 when that change is pursuant to General Rule of Interpretation 2(a).

corpus holds (('8716.10-8716.80',), (('any_other', 'heading'), ('named', '')), ()), CBP quoted (('8716.10-8716.80',), (('any_other', 'heading'),), ())

**560996** (1998) — `differs`

> A change to heading 3922 through 3926 from any other heading, including another heading within that group.

corpus holds (('3922-3926',), (('any_other', 'subheading'),), ('3901-3914', '3926', '9619')), CBP quoted (('3922-3926',), (('any_other', 'heading'),), ())

**561037** (1998) — `target_absent`

> A change to subheading 8525.10 through 8525.20 from any other subheading outside that group.

no rule in the corpus targets 8525.10

**561103** (1999) — `target_absent`

> A change to subheading 8103.10 through 8113.00 from any other subheading, including another subheading within that group; or A change to any of the following goods classified in subheading 8103.10 through 8113.00, including from materials also classified in subheading 8103.10 through 8113.00: Matte; unwrought; powder except from flakes; flakes except from powder; bars except from rods or profiles;

no rule in the corpus targets 8103.10

**561210** (1999) — `differs`

> A change to subheading 9503.50 through 9503.60 from any other subheading including another subheading within that group.

corpus holds (('9503',), (('any_other', 'chapter'),), ()), CBP quoted (('9503.50-9503.60',), (('any_other', 'subheading'),), ())

**561291** (2000) — `target_absent`

> A change to subheading 8525.10 through 8525.20 from any other subheading outside that group.

no rule in the corpus targets 8525.10

**561370** (1999) — `target_absent`

> A change to subheading 8525.30 through 8525.40 from any other subheading, including another subheading within that group, except a change to video camera recorders of subheading 8525.40 from television cameras of subheading 8525.30.

no rule in the corpus targets 8525.30

**561457** (1999) — `target_absent`

> A change to subheading 3824.71 through 3824.90 from any other subheading, including another subheading within that group, provided that no more than 60 percent by weight of the good classified in this subheading is attributable to one substance or compound.

no rule in the corpus targets 3824.71

**561488** (1999) — `target_absent`

> A change to subheading 8103.10 through 8113.00 from any other subheading, including another subheading within that group; or A change to any of the following goods classified in subheading 8103.10 through 8113.00, including from materials also classified in subheading 8103.10 through 8113.00: Matte; wrought; powder except from flakes; flakes except from powder; bars except from rods or profiles; r

no rule in the corpus targets 8103.10

**561520** (2000) — `target_absent`

> A change to heading 8524 from any other heading.

no rule in the corpus targets 8524

**561735** (2001) — `differs`

> A change to heading 3922 through 3926 from any other heading, including another heading within that group.

corpus holds (('3922-3926',), (('any_other', 'subheading'),), ('3901-3914', '3926', '9619')), CBP quoted (('3922-3926',), (('any_other', 'heading'),), ())

**561736** (2001) — `differs`

> A change to subheading 8505.11 through 8505.30 from any other subheading, including another subheading within that group.

corpus holds (('8505.11-8505.20',), (('any_other', 'subheading'),), ()), CBP quoted (('8505.11-8505.30',), (('any_other', 'subheading'),), ())

**561989** (2001) — `target_absent`

> A change to subheading 8708.31 from any other heading, except to mounted brake linings and pads of 8708.31 from subheading 6813.10.

no rule in the corpus targets 8708.31

**562012** (2001) — `target_absent`

> A change to subheading 9021.19 from any other subheading, except from nails classified in heading 7317 or screws classified in heading 7318 when resulting from a simple assembly.

no rule in the corpus targets 9021.19

**562161** (2001) — `differs`

> A change to heading 4901 through 4911 from any other heading, including another heading within that group.

corpus holds (('4901-4908',), (('any_other', 'heading'),), ()), CBP quoted (('4901-4911',), (('any_other', 'heading'),), ())

**562161** (2001) — `unparsed`

> a change to another heading

the quotation does not parse as a rule

**562497** (2002) — `target_absent`

> A change to subheading 3006.20 through 3006.60 from any other subheading, including another subheading within that group.

no rule in the corpus targets 3006.20

**562595** (2002) — `target_absent`

> A change to subheading 8525.10 through 8525.20 from any other subheading outside that group.

no rule in the corpus targets 8525.10

**735447** (1994) — `differs`

> A change to subheading 8539.10 through 8539.40 from any other subheading, including another subheading within that group.

corpus holds (('8539.10-8539.31',), (('any_other', 'subheading'),), ()), CBP quoted (('8539.10-8539.40',), (('any_other', 'subheading'),), ())

**735450** (1994) — `target_absent`

> A change to subheading 8509.10 through 8509.80 from any other subheading, including another subheading within that group.

no rule in the corpus targets 8509.10

**735450** (1994) — `unparsed`

> a change to this classification from any other subheading, which includes the "parts" subheading 8509.90.

the quotation does not parse as a rule

**735496** (1994) — `target_absent`

> A change to heading 0405 through 0406 from any other heading, including another heading within that group.

no rule in the corpus targets 0405

**735538** (1994) — `differs`

> A change to subheading 8708.10 through 8708.29 from any other subheading.

corpus holds (('8708.10',), (('any_other', 'subheading'),), ()), CBP quoted (('8708.10-8708.29',), (('any_other', 'subheading'),), ())

**735542** (1994) — `target_absent`

> A change to subheading 8509.10 from any other heading, except heading 8501 when resulting from simple assembly.

no rule in the corpus targets 8509.10

**735554** (1995) — `differs`

> A change to heading 7010 through 7018 from any other heading, except from heading 7020; or A change to heading 7010 through 7018 from heading 7020 if that change results in a substantial transformation In this case

corpus holds (('7010',), (('any_other', 'heading'),), ()), CBP quoted (('7010-7018',), (('any_other', 'heading'),), ('7020',))

**735588** (1995) — `differs`

> A change to 7010 through 7018 from any other heading, except from heading 7020; or .

corpus holds (('7010',), (('any_other', 'heading'),), ()), CBP quoted (('7010-7018',), (('any_other', 'heading'),), ('7020',))

**735588** (1995) — `differs`

> A change to heading 7010 through 7018 from heading 7020 if that change results in a substantial transformation.

corpus holds (('7010',), (('any_other', 'heading'),), ()), CBP quoted (('7010-7018',), (('named', ''),), ())

**955371** (1994) — `unparsed`

> a change to those headings: from any other heading outside that group, except headings 6501 through 6502; or from heading 6501 by means of a blocking process; or from heading 6502, provided that the change is the result of at least three processing steps (e.

the quotation does not parse as a rule

**955807** (1994) — `target_absent`

> A change to subheading of heading 7113 through 7115 from any other subheading, including to a subheading within that group.

no rule in the corpus targets 7113

**955808** (1994) — `target_absent`

> A change to subheading of heading 7113 through 7115 from any other subheading, including to a subheading within that group.

no rule in the corpus targets 7113

**955809** (1994) — `target_absent`

> A change to subheading of heading 7113 through 7115 from any other subheading, including to a subheading within that group.

no rule in the corpus targets 7113

**956240** (1995) — `differs`

> a change to subheading 9404.90 from any other heading satisfies the tariff classification shift provisions set forth in Section 102.11(a)(3).

corpus holds (('9404.30-9404.90',), (('any_other', 'heading'),), ()), CBP quoted (('9404.90',), (('any_other', 'heading'),), ())

**956936** (1995) — `differs`

> a change to subheading 9404.90 from any other heading for goods classifiable under subheading 9404.90, HTSUSA, to be considered goods of a NAFTA party for country of origin marking purposes.

corpus holds (('9404.30-9404.90',), (('any_other', 'heading'),), ()), CBP quoted (('9404.90',), (('any_other', 'heading'),), ())

**963300** (2001) — `differs`

> A change to heading 1501 through 1515 from any other chapter.

corpus holds (('1501-1516',), (('any_other', 'chapter'),), ()), CBP quoted (('1501-1515',), (('any_other', 'chapter'),), ())

**H242892** (2014) — `target_absent`

> A change to heading 1601-1605 from any other chapter, except from smoked products of heading 0306 through 0308.

no rule in the corpus targets 1601

**H254791** (2014) — `target_absent`

> a change to subheading 9608 through 9608.40 from any other subheading, including another subheading within that group except subheading 9608.60.

no rule in the corpus targets 9608.00

**H263571** (2015) — `differs`

> a change to heading 4818 from sanitary towels and tampons, napkin and napkin liners for babies, and similar sanitary articles, of paper pulp, paper, cellulose wadding, or webs of cellulose fibers, of heading 9619.

corpus holds (('4817-4822',), (('any_other', 'heading'),), ('4818', '9619')), CBP quoted (('4818',), (('named', ''),), ())

**H265611** (2015) — `unparsed`

> a change to a subheading from another subheading of the same heading, the rule will be satisfied only if the change is from a subheading of the same level specified in the rule.

the quotation does not parse as a rule

**H281296** (2017) — `differs`

> A change to a good of subheading 2106.90, other than to compound alcoholic preparations, from any other subheading, except from Chapter 4, Chapter 17, heading 2009, subheading 1901.90 or subheading 2202.90; or * * * A change to subheading 2106.90 from Chapter 17, provided that the good contains less than 65 percent by dry weight of sugar.

corpus holds (('2106.90',), (('any_other', 'subheading'),), ('04', '1602.90', '17', '1901.90', '2009', '2202.91', '2202.99', '2404.91', '3006.93')), CBP quoted (('2106.90',), (('any_other', 'subheading'),), ('04', '17', '1901.90', '2009', '2106.90', '2202.90'))

**H290625** (2022) — `differs`

> A change to any other good of subheading 3920.10 through 3920.90 from any other subheading, including another subheading within that group.

corpus holds (('3920.10-3921.90',), (('any_other', 'subheading'),), ()), CBP quoted (('3920.10-3920.90',), (('any_other', 'subheading'),), ())

**H290625** (2022) — `differs`

> a change to a good of subheading 3920.62 from subheading 3907.60

corpus holds (('3920.10-3921.90',), (('any_other', 'subheading'),), ()), CBP quoted (('3920.62',), (('named', ''),), ())

**H296462** (2018) — `differs`

> A change to a good of subheading 2106.90, other than to compound alcoholic preparations, from any other subheading, except from Chapter 4, Chapter 17, heading 2009, subheading 1901.90 or subheading 2202.90; or * * * A change to subheading 2106.90 from Chapter 17, provided that the good contains less than 65 percent by dry weight of sugar.

corpus holds (('2106.90',), (('any_other', 'subheading'),), ('04', '1602.90', '17', '1901.90', '2009', '2202.91', '2202.99', '2404.91', '3006.93')), CBP quoted (('2106.90',), (('any_other', 'subheading'),), ('04', '17', '1901.90', '2009', '2106.90', '2202.90'))

**H303919** (2019) — `differs`

> A change to subheading 8543.70 from any other subheading, except from proximity cards or tags of subheading 8523.52 and except from other machines or apparatus of subheading 8486.10 through 8486.20.

corpus holds (('8543.70',), (('any_other', 'subheading'),), ('8486.10-8486.20', '8523.52', '8539.51', '8539.52')), CBP quoted (('8543.70',), (('any_other', 'subheading'),), ('8486.10-8486.20', '8523.52'))

**H304107** (2019) — `differs`

> A change to subheading 8544.42 from any good of subheading 8544.42, except when resulting from a simple assembly; or * * * A change to subheading 8544.11 through 8544.70 from any other subheading, including another subheading within that group, except when resulting from simple assembly.

corpus holds (('8544.42',), (('same_position', 'subheading'),), ()), CBP quoted (('8544.42',), (('same_position', 'subheading'),), ('8544.11-8544.70',))

**H304108** (2019) — `differs`

> A change to subheading 8544.42 from any good of subheading 8544.42, except when resulting from a simple assembly; or * * * A change to subheading 8544.11 through 8544.70 from any other subheading, including another subheading within that group, except when resulting from simple assembly.

corpus holds (('8544.42',), (('same_position', 'subheading'),), ()), CBP quoted (('8544.42',), (('same_position', 'subheading'),), ('8544.11-8544.70',))

**H314566** (2021) — `differs`

> A change to subheading 8512.90 from any other subheading.

corpus holds (('8512.90',), (('any_other', 'heading'),), ()), CBP quoted (('8512.90',), (('any_other', 'subheading'),), ())

**H334088** (2024) — `differs`

> A change to naphthenic acids, their water-insoluble salts or their esters of subheading 3824.90 from any other good of subheading 3824.90 or from any other subheading; or A change to any other good of subheading 3824.90 from naphthenic acids, their water-insoluble salts or their esters of subheading 3824.90 or from any other subheading, provided that no more than 60 percent by weight of the good c

corpus holds (('3824.84-3824.99', '3824.99'), (('any_other', 'subheading'),), ()), CBP quoted (('3824.90',), (('any_other', 'subheading'), ('same_position', 'subheading')), ())

**H341208** (2025) — `differs`

> a change to heading 3926 from articles of apparel and clothing accessories, other articles of plastics, or articles of other materials of headings 3901 to 3914 of heading 9619.

corpus holds (('3922-3926',), (('any_other', 'subheading'),), ('3901-3914', '3926', '9619')), CBP quoted (('3926',), (('named', ''),), ())

**H341787** (2025) — `differs`

> A change to naphthenic acids, their water-insoluble salts or their esters of subheading 3824.90 from any other good of subheading 3824.90 or from any other subheading; or A change to any other good of subheading 3824.90 from naphthenic acids, their water-insoluble salts or their esters of subheading 3824.90 or from any other subheading, provided that no more than 60 percent by weight of the good c

corpus holds (('3824.84-3824.99', '3824.99'), (('any_other', 'subheading'),), ()), CBP quoted (('3824.90',), (('any_other', 'subheading'), ('same_position', 'subheading')), ())

**H342474** (2025) — `unparsed`

> A change to color video monitors from any other good of subheading 8528.59 or from any other subheading, except from subheading 8540.11 through 8540.12; or A change to black and white or other monochrome video monitors from any other good of subheading 8528.59 or from any other subheading, except from subheading 8540.11 through 8540.12.

the quotation does not parse as a rule

**W562873** (2003) — `target_absent`

> A change to subheading 8528.12 through 8528.30 from any other subheading, including another subheading in that group, except from 8540.11 through 8540.12 Under the facts provided, foreign component materials initially classifiable in headings 3506, 3919, 3926, 4821, 4901, 4911, 5602, 7009, 7316, 7318, 7326, 7616, 8471, 8504, 8518, 8529, 8536, 8539, 8544, 9001, 9612, HTSUS, and subheading 8540.40.

no rule in the corpus targets 8528.12

## Reproducing this

```
pip install -e ".[dev]"
python -m originshift.validate --fetch   # the CROSS rulings, ~5 min
python -m originshift.validate           # print
python -m originshift.validate --emit docs/validation.md
```

