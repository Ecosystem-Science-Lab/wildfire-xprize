<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# What organizations in Australia operate satellite direct broadcast ground stations that receive VIIRS, MODIS, or other polar-orbiting weather satellite data in near-real-time? I'm looking for potential data partnerships for a wildfire detection competition in NSW Australia. Specifically: 1) Does the Australian Bureau of Meteorology (BoM) operate HRPT/direct broadcast receivers? Do they share data? 2) Does Geoscience Australia have real-time satellite reception capability? 3) What about CSIRO? 4) Are there any Australian universities with satellite ground stations (e.g., UNSW Canberra, University of Tasmania)? 5) Does the Australian Antarctic Division operate receivers that could capture VIIRS passes over southeastern Australia? 6) Are there any commercial providers in Australia offering near-real-time VIIRS/MODIS data (e.g., GEOIMAGE, DigitalGlobe/Maxar partners)? 7) What about the Satellite Remote Sensing facility at the Bureau of Meteorology in Melbourne? 8) Does the Australian Space Agency have any relevant partnerships? 9) Are there international direct broadcast networks (like the International Polar-Orbiting Partnership) that share data from Australian region stations? 10) What about NovaSAR or other facilities at the Weilheim, Svalbard, or McMurdo stations that might capture passes over Australia?

Australia has a fairly rich ecosystem of near–real‑time polar‑orbiting reception, centered on the Bureau of Meteorology (BoM), Geoscience Australia (Digital Earth Australia), CSIRO/IMOS partners, and Landgate/WASTAC, with additional commercial capacity at Alice Springs and smaller university ground stations.[^1_1][^1_2][^1_3][^1_4][^1_5]

Below I go through your 10 questions one by one, then suggest who to actually contact for a NSW wildfire competition.

***

## 1) Bureau of Meteorology HRPT / direct broadcast and data sharing

BoM operates and coordinates a network of polar‑orbiting satellite reception stations that receive High Resolution Picture Transmission (HRPT) direct broadcast data from NOAA and related missions at Darwin, Melbourne and Australian Antarctic stations, with Perth handled via WASTAC.[^1_6][^1_7][^1_8][^1_1]
As part of IMOS’ Satellite Remote Sensing facility, BoM and partners ingest locally received HRPT AVHRR data from stations in Darwin, Melbourne, Hobart, Perth, Townsville, Alice Springs, Casey and Davis and turn it into real‑time GHRSST‑format SST products that are openly distributed via IMOS and GHRSST servers.[^1_9][^1_10][^1_11][^1_1]

BoM has transitioned from AVHRR‑only to also using VIIRS SST products: it composites NOAA CoastWatch VIIRS L3U SST onto the IMOS grid and distributes multi‑sensor SST fields for the Australian region.[^1_12][^1_13]
BoM is also a member of the WMO Direct Broadcast Network (DBNet) for the Asia‑Pacific region, meaning data from its HRPT stations is redistributed globally in near‑real‑time via the WMO Information System / GTS to NWP centers and other users.[^1_14][^1_15][^1_16][^1_17]

**Data access / sharing.**
BoM‑processed products (e.g., GHRSST SST fields) are openly available via IMOS/AODN portals and GHRSST, but raw HRPT streams are normally disseminated through WMO mechanisms (AP‑RARS/DBNet) or bilateral arrangements rather than as an open fire‑hose.[^1_10][^1_18][^1_1][^1_9]
For direct collaboration, BoM lists a contact for Asia‑Pacific RARS/DBNet operations (Satellite Operations group, satellites@bom.gov.au) on its AP‑RARS page, which is the correct entry point if you want to discuss near‑real‑time polar‑orbiting feeds for research or competitions.[^1_8][^1_6]

***

## 2) Geoscience Australia real‑time reception (Digital Earth Australia)

Geoscience Australia (GA) operates the Alice Springs satellite ground station, which performs daily downlinks from multiple missions, including NOAA, Terra, Aqua, Sentinel, and Suomi‑NPP, and provides coverage for the entire Australian continent.[^1_19][^1_20]
GA’s Digital Earth Australia (DEA) Hotspots system explicitly uses directly received telemetry at Alice Springs for MODIS, AVHRR and VIIRS, which is converted to Level 0 / Raw Data Record and then processed into fire‑detection inputs.[^1_4]

DEA Hotspots is a **national bushfire monitoring system** that ingests MODIS, AVHRR and VIIRS thermal channels plus Himawari‑9, updates approximately every 10 minutes, and can deliver hotspot detections with best‑case latency of about 17 minutes after satellite overpass.[^1_21][^1_22][^1_4]
The DEA Hotspots dataset description confirms that VIIRS on Suomi‑NPP (and now also NOAA‑21) is one of the hotspot sources, and that web services (WMS, etc.) are the supported access mechanism for external users.[^1_23][^1_22]

**For your competition:** DEA Hotspots is already an operational, near‑real‑time MODIS/VIIRS fire product for all of Australia, and GA provides web services and contact details (earth.observation@ga.gov.au) specifically for external users and emergency managers.[^1_22][^1_23]

***

## 3) CSIRO near‑real‑time reception

CSIRO is a long‑standing partner in Australia’s HRPT and X‑band receiving network and in WASTAC, and operates/has operated ground segment facilities in Hobart and Western Australia.[^1_7][^1_2][^1_3][^1_24]
IMOS/CSIRO documentation notes that high‑resolution AVHRR HRPT data downlinked since the early 1980s from Perth (WASTAC), Darwin and Melbourne (BoM), Hobart (CSIRO) and Townsville (AIMS) are combined to produce national‑coverage SST fields, which are then made available through IMOS.[^1_2][^1_11]

CSIRO also runs the **NovaSAR‑1 national facility**, using the Aboriginal‑owned CfAT/Viasat ground station near Alice Springs to downlink L‑band SAR data which is then processed and shared with registered research users.[^1_25][^1_5]
While NovaSAR‑1 is not a thermal imager like VIIRS/MODIS, its SAR data is potentially useful for burn‑scar mapping, fuel moisture proxies, and landscape change, though revisit/latency are typically hours to days rather than minutes.[^1_25]

***

## 4) University ground stations (UNSW Canberra, UTas, WASTAC‑linked)

**UNSW Canberra Space.** UNSW Canberra operates two ground stations (main site near Yass, NSW, and a backup/test station on the ADFA campus) that support UHF and S‑band communications for its CubeSats (e.g., the M2 Pathfinder mission performed telemetry and data downlinks via the Yass ground station).[^1_26][^1_27][^1_28][^1_29]
These are mission‑specific TT\&C/data‑downlink facilities rather than general‑purpose HRPT weather‑satellite receivers, but they indicate local expertise and infrastructure if you ever consider a dedicated fire‑detection cubesat.

**WASTAC university partners.** The Western Australian Satellite Technology and Applications Consortium (WASTAC) historically operated NOAA/MODIS (and later VIIRS) receiving antennas located at Curtin and Murdoch Universities in Perth, and remains focused on near‑real‑time MODIS/AVHRR/VIIRS data for Western Australia and surrounding oceans.[^1_3][^1_30][^1_24]
WASTAC annual reports describe a near‑real‑time quick‑look archive of VIIRS, MODIS and AVHRR data maintained by Landgate’s Earth Observation team, with coverage back to 1983 for AVHRR, 2001 for MODIS and 2012 for VIIRS, available to partners on request.[^1_31][^1_30][^1_3]

**University of Tasmania \& IMOS.** The University of Tasmania leads IMOS and hosts the eMarine Information Infrastructure, while HRPT polar‑orbiting reception in Hobart has been operated by CSIRO and the former Tasmanian Earth Resources Satellite Station (TERSS).[^1_32][^1_33][^1_1]
So UTas is a key programmatic and data hub rather than the owner of a standalone VIIRS/MODIS DB antenna today.

***

## 5) Australian Antarctic Division receivers and coverage of SE Australia

BoM’s AP‑RARS / DBNet table lists Casey and Davis stations in Antarctica as BoM‑operated HRPT/ATOVS sites, forming part of the Asia‑Pacific Regional ATOVS Retransmission Service and the wider Direct Broadcast Network.[^1_6][^1_1][^1_7][^1_8]
The “Bureau Coverage” description notes that the combined Australian reception stations on the mainland and Antarctic stations together provide coverage from the South Pole to north of the equator, and from New Zealand to well west of Perth.[^1_8]

In practice, the Antarctic receivers at Casey and Davis are primarily used for high‑southern‑latitude and Southern Ocean coverage; the mainland HRPT sites (Darwin, Melbourne, Perth/WASTAC, Townsville, Hobart, Alice Springs) are what give dense coverage over southeastern Australia.[^1_1][^1_2][^1_8]
So while Casey/Davis are part of the same HRPT/DBNet/AP‑RARS network that eventually feeds Australian and global products, they are not your primary route to VIIRS data over NSW; the mainland stations and DEA/BoM products are better suited for that.[^1_4][^1_1][^1_8]

***

## 6) Commercial near‑real‑time VIIRS/MODIS data providers in Australia

**Landgate / WASTAC quick‑look services.** WASTAC reports describe a near‑real‑time “quick‑look” archive of MODIS, AVHRR and VIIRS data operated by Landgate’s Earth Observation team, supporting applications such as flood and water‑extent mapping, with archive coverage since 1983 (AVHRR), 2001 (MODIS) and 2012 (VIIRS).[^1_30][^1_24][^1_3][^1_31]
Although primarily aimed at WA and Indian Ocean users, Landgate is an obvious contact for near‑real‑time VIIRS/MODIS imagery and fire‑related services under commercial or inter‑agency agreements.

**CfAT / Viasat Real‑Time Earth (Alice Springs).** The Centre for Appropriate Technology (CfAT) and Viasat have built an indigenous‑owned Real‑Time Earth ground station complex at Alice Springs, hosting multiple state‑of‑the‑art Earth‑observation ground stations as part of Viasat’s global Real‑Time Earth GSaaS network.[^1_34][^1_5][^1_35][^1_36]
The facility is explicitly marketed for low‑latency downlink of LEO Earth‑observation satellites for applications such as disaster management (including bushfires), environmental monitoring and border protection, and can see passes over all of mainland Australia from its central location.[^1_5][^1_35][^1_37]

Global GSaaS providers like RBC Signals and KSAT are also identified in wildfire‑mission studies as potential providers of near‑real‑time coverage over Australia using stations at Alice Springs and elsewhere, though they typically serve custom satellites rather than NOAA/JPSS directly.[^1_38][^1_37]
I could not find evidence that GEOIMAGE or a Maxar/WorldView reseller in Australia operates their own HRPT/VIIRS‑class direct‑broadcast station; they generally consume upstream NRT products (e.g., NASA LANCE) rather than operating weather‑satellite ground segments themselves.[^1_39][^1_40]

***

## 7) BoM’s Satellite Remote Sensing facility in Melbourne

The **IMOS Satellite Remote Sensing – Satellite SST Sub‑Facility** is explicitly operated by the Australian Bureau of Meteorology and produces high‑resolution (1 km) SST products over the Australian region using locally received HRPT AVHRR data and, more recently, VIIRS SST products.[^1_13][^1_18][^1_9][^1_10]
This facility combines raw HRPT data from ground stations in Darwin, Townsville, Melbourne, Hobart, Perth, Alice Springs, Casey and Davis into real‑time GHRSST‑format L2P/L3U/L3C/L3S SST products, which are distributed via IMOS servers and the AODN portal for open research use.[^1_11][^1_9][^1_10][^1_1]

Although the operational focus is ocean temperature rather than fire, the key point for you is that the Melbourne‑based BoM/IMOS Satellite Remote Sensing facility is already running end‑to‑end near‑real‑time processing chains for locally received polar‑orbiting data, including VIIRS SST, and sharing the resulting gridded products freely.[^1_18][^1_9][^1_10][^1_13]
That group (often led by Helen Beggs and colleagues in recent reports) is a very relevant technical counterpart if you want to explore extending or repurposing polar‑orbiting feeds for fire monitoring experiments.[^1_12][^1_13][^1_18]

***

## 8) Australian Space Agency partnerships

The Australian Space Agency does **not** operate its own polar‑orbit ground stations, but it plays a coordinating role for Earth‑observation policy and infrastructure and explicitly points to partnerships with GA, BoM and CSIRO as the way Australia secures satellite EO data.[^1_41][^1_42][^1_43]
The national “Earth Observation from Space Roadmap 2021–2030” and the Bushfire Earth Observation Taskforce report both emphasize partnerships (with NASA, USGS, ESA and others) and better coordination of existing ground‑segment assets rather than new government‑run stations.[^1_42][^1_43]

Geoscience Australia notes that the **Australian National Ground Segment Technical Team (ANGSTT)** coordinates the national network of EO ground stations, listing collaborators including Geoscience Australia, BoM, CSIRO, Landgate (WA) and the Australian Space Agency.[^1_20]
For a NSW wildfire‑detection challenge that wants to leverage existing Australian stations, approaching the Agency as a high‑level convenor (while technically negotiating with GA/BoM/Landgate) could help frame it as a national demonstrator rather than a one‑off project.[^1_42][^1_20]

***

## 9) International direct‑broadcast networks using Australian stations

**DBNet and AP‑RARS.** The WMO Direct Broadcast Network (DBNet) generalizes the earlier Regional ATOVS Retransmission Service (RARS) concept to provide near‑global, near‑real‑time access to LEO sounder and imager data (ATOVS, ATMS, CrIS, IASI, VIIRS, AVHRR, etc.) via a network of HRPT / direct broadcast stations, including an Asia‑Pacific regional network.[^1_15][^1_44][^1_45][^1_14]
BoM is explicitly identified as participating in DBNet for Asia‑Pacific, and AP‑RARS documentation shows Australian HRPT sites (including mainland and Antarctic stations) feeding a regional retransmission system whose purpose is rapid delivery of polar‑orbiting data to the global user community.[^1_16][^1_17][^1_8]

**NASA/NOAA direct‑broadcast networks and FIRMS.** NASA’s FIRMS and related systems use a network of MODIS/VIIRS X‑band direct‑broadcast stations worldwide, plus central downlinks, to generate ultra‑real‑time fire products “within a few minutes of observation,” and those include Australia in their coverage.[^1_46][^1_47][^1_48]
The SSEC real‑time feed listing explicitly shows NOAA‑18/19 AVHRR HRPT data being received in Cape Ferguson, Australia (AIMS Townsville) and relayed into the global network, alongside data from stations like Gilmore (Fairbanks), Svalbard and Wallops.[^1_49][^1_50]

So yes—there are international direct‑broadcast / NRT networks (WMO’s DBNet/AP‑RARS, NASA’s FIRMS direct‑readout network, and related SSEC/NWP‑SAF systems) that already aggregate data from Australian ground stations and redistribute it in near‑real‑time globally.[^1_47][^1_50][^1_44][^1_49][^1_14][^1_8]
For a competition, the most practical “international” NRT sources you can tap without bespoke agreements are NASA LANCE / FIRMS APIs and DEA Hotspots (which itself uses both domestic and international satellite feeds).[^1_48][^1_46][^1_22][^1_4]

***

## 10) NovaSAR and high‑latitude stations (Weilheim, Svalbard, McMurdo)

**NovaSAR‑1 (CSIRO).** NovaSAR‑1 is an L‑band SAR satellite with an Australian national research facility operated by CSIRO; images are downlinked via the CfAT/Viasat Real‑Time Earth ground station at Alice Springs and then processed and made available to registered facility users.[^1_5][^1_25]
It is not a weather satellite and does not carry a VIIRS/MODIS‑like imager, but could complement thermal fire‑detection with SAR‑based products (burn severity, inundation, vegetation structure), subject to tasking and revisit constraints.[^1_25]

**Svalbard, McMurdo, Weilheim.** Suomi‑NPP and similar polar‑orbiters downlink once per orbit to high‑latitude core ground stations such as Svalbard (Norway) and McMurdo (Antarctica), and then relay the data to central processing centers, which in turn feed NRT products like VIIRS Corrected Reflectance and active fires.[^1_51][^1_46][^1_48]
Those stations do **not** extend the line‑of‑sight for direct‑broadcast reception over Australia; instead, they are the backbone for global NRT products (NASA LANCE, NOAA services, EUMETSAT EARS), which you already consume indirectly via FIRMS, DEA products, etc.[^1_46][^1_48][^1_14][^1_15]

So for Australian wildfire use‑cases, leveraging Svalbard/McMurdo/Weilheim realistically means using **their processed global NRT outputs** (e.g., LANCE/FIRMS, NOAA/OSPO NRT, EUMETSAT services), rather than forming a direct partnership with those ground stations themselves.[^1_52][^1_47][^1_48][^1_46]

***

## Practical partners to approach for a NSW wildfire detection competition

If your goal is to stand up a near‑real‑time satellite stream for a NSW‑focused wildfire competition, these are the most actionable organizations and entry points:

- **Digital Earth Australia Hotspots (Geoscience Australia):** existing national MODIS/AVHRR/VIIRS fire product with ~10–20 min latency and APIs/web services; technical contact via earth.observation@ga.gov.au.[^1_21][^1_23][^1_22][^1_4]
- **BoM Satellite Operations / IMOS Satellite Remote Sensing sub‑facility (Melbourne):** managers of the HRPT polar‑orbit network and IMOS SST processing; contact via Satellite Operations (AP‑RARS/DBNet) and the IMOS SRS SST sub‑facility.[^1_9][^1_10][^1_18][^1_6][^1_8]
- **Landgate / WASTAC EO team (Western Australia):** operators of a near‑real‑time quick‑look archive of VIIRS/MODIS/AVHRR over Australia and WA, with strong fire/flood mapping experience.[^1_53][^1_3][^1_31][^1_30]
- **CfAT Satellite Enterprises / Viasat Real‑Time Earth (Alice Springs):** commercial GSaaS provider for low‑latency LEO EO data over all of Australia, including potential custom tasking for future fire missions.[^1_35][^1_36][^1_34][^1_5]
- **Australian National Ground Segment Technical Team (ANGSTT):** coordination forum including GA, BoM, CSIRO, Landgate and the Australian Space Agency, useful if you want the exercise framed as a national ground‑segment demonstration.[^1_41][^1_20][^1_42]

If you’d like, I can help you design a competition data package that combines DEA Hotspots, NASA FIRMS/LANCE NRT VIIRS/MODIS, and optionally Himawari‑9, with clear latency and coverage guarantees for NSW.
<span style="display:none">[^1_100][^1_101][^1_102][^1_103][^1_104][^1_105][^1_54][^1_55][^1_56][^1_57][^1_58][^1_59][^1_60][^1_61][^1_62][^1_63][^1_64][^1_65][^1_66][^1_67][^1_68][^1_69][^1_70][^1_71][^1_72][^1_73][^1_74][^1_75][^1_76][^1_77][^1_78][^1_79][^1_80][^1_81][^1_82][^1_83][^1_84][^1_85][^1_86][^1_87][^1_88][^1_89][^1_90][^1_91][^1_92][^1_93][^1_94][^1_95][^1_96][^1_97][^1_98][^1_99]</span>

<div align="center">⁂</div>

[^1_1]: https://researchdata.edu.au/imos-srs-satellite-sub-facility/476861

[^1_2]: https://www.cmar.csiro.au/remotesensing/oceancurrents/sourcedata/

[^1_3]: https://www.angstt.gov.au/about/annual-reports/Annual-Report-2018.pdf

[^1_4]: https://hotspots.dea.ga.gov.au/cache/DEA+Hotspots+-+Product+Description+-+Version+2.0.pdf

[^1_5]: https://cfat.org.au/cfat-se-1

[^1_6]: http://www.bom.gov.au/australia/satellite/rars.shtml

[^1_7]: https://www.isprs.org/proceedings/2011/isrse-34/211104015Final00888.pdf

[^1_8]: https://www.bom.gov.au/australia/satellite/rars.shtml

[^1_9]: https://researchdata.edu.au/imos-satellite-remote-sub-facility/3977939?fl

[^1_10]: https://researchdata.edu.au/imos-srs-satellite-sub-facility/3000421

[^1_11]: https://oceancurrent.aodn.org.au/sourcedata/

[^1_12]: https://www.star.nesdis.noaa.gov/data/star_docs/meetings/2017JPSSAnnual/SST/05_BoM_Use_of_VIIRS_SST_Beggs_v02.pdf

[^1_13]: https://imos.org.au/wp-content/uploads/2024/07/Beggs_2019_IMOS_Multi-sensor_L3S_article_21Feb2018.pdf

[^1_14]: https://www-cdn.eumetsat.int/files/2020-04/pdf_wmo_dvbnet_guide.pdf

[^1_15]: https://community.wmo.int/site/knowledge-hub/programmes-and-initiatives/wmo-space-programme-wsp/data-access-and-use-1

[^1_16]: https://www.industry.gov.au/sites/default/files/2024-02/state-of-space-report-2021.pdf

[^1_17]: https://www.space.gov.au/sites/default/files/media-documents/2023-04/state-of-space-report-2021.pdf

[^1_18]: https://imos.org.au/wp-content/uploads/2024/07/Beggs_Australian_RDAC_Report_to_GXX_2019_v3.pdf

[^1_19]: https://www.ga.gov.au/scientific-topics/space/our-satellite-and-ground-station-network

[^1_20]: https://www.ga.gov.au/news/40-years-of-landsat-in-australia

[^1_21]: https://www.spatialsource.com.au/shining-a-spotlight-on-bushfire-monitoring/

[^1_22]: https://knowledge.dea.ga.gov.au/data/product/dea-hotspots/index.html

[^1_23]: https://researchdata.edu.au/digital-earth-australia-hotspots-dataset/3431940

[^1_24]: https://www.angstt.gov.au/__data/assets/pdf_file/0007/112696/annual_report_2007.pdf

[^1_25]: https://www.csiro.au/en/news/all/articles/2021/july/novasar-1-research-facility

[^1_26]: https://www.unsw.edu.au/canberra/our-research/our-facilities/satellite-ground-stations

[^1_27]: https://www.australiandefence.com.au/defence/cyber-space/unsw-and-raaf-launch-m2-pathfinder-satellite

[^1_28]: https://www.spaceconnectonline.com.au/launch/4391-raaf-unsw-canberra-launch-cubesat-on-rocket-lab-launch-mission

[^1_29]: https://www.spaceconnectonline.com.au/r-d/5062-unsw-raaf-satellite-successfully-separates-for-deeper-research

[^1_30]: https://www.angstt.gov.au/about/annual-reports/annual_report_2017.pdf

[^1_31]: https://www.angstt.gov.au/about/annual-reports/annual_report_2014.pdf

[^1_32]: https://unfccc.int/resource/docs/gcos/ausgcos.pdf

[^1_33]: https://citeseerx.ist.psu.edu/document?doi=9473bb37bf1771f289044b7e11e374364cfa87f3\&repid=rep1\&type=pdf

[^1_34]: https://www.viasat.com/news/latest-news/government/2020/viasats-real-time-earth-ground-station-now-open-in-australia/

[^1_35]: https://www.spaceconnectonline.com.au/satellites/3461-viasat-to-work-with-indigenous-centre-for-appropriate-tech-on-satellite-network

[^1_36]: https://spacewatch.global/2020/07/australia-goes-live-with-1st-indigenous-satellite-ground-station/

[^1_37]: https://smartsatcrc.lbcdn.io/uploads/Tech-report-10-WildFireSat-Preliminary-Suitability-Assessment.pdf

[^1_38]: https://www.gmv.com/sites/default/files/content/file/2023/01/19/114/gmv_news_84_en_0.pdf

[^1_39]: https://www.science.gov/topicpages/n/near-real+time+satellite

[^1_40]: https://modis.gsfc.nasa.gov

[^1_41]: https://www.unoosa.org/documents/pdf/Space4SDGs/Space2030/Australia_A.pdf

[^1_42]: https://www.industry.gov.au/sites/default/files/January 2022/document/earth_observation_from_space_roadmap.pdf

[^1_43]: https://www.space.gov.au/sites/default/files/media-documents/2023-11/Bushfire Earth Observation Taskforce Report.pdf

[^1_44]: https://nmsc.kma.go.kr/enhome/html/base/cmm/selectPage.do?page=activities.dbnet.dbnetInformation

[^1_45]: https://itwg.ssec.wisc.edu/wordpress/wp-content/uploads/2023/05/oral.16.02.Rattenborg-Mikael-Rattenborg_itsc24.pdf

[^1_46]: https://www.earthdata.nasa.gov/data/instruments/viirs/land-near-real-time-data

[^1_47]: https://earthdata.nasa.gov/s3fs-public/2025-06/arset-firms2025-part2-slides.pdf

[^1_48]: https://www.earthdata.nasa.gov/data/instruments/modis/near-real-time-data

[^1_49]: https://imos.org.au/facility/satellite-remote-sensing/ground-stations

[^1_50]: https://www.ssec.wisc.edu/datacenter/real-time.html

[^1_51]: https://www.asianscientist.com/2012/12/topnews/nasa-noaa-suomi-npp-satellite-takes-pictures-of-australian-wildfires-2012/

[^1_52]: https://www.eoportal.org/other-space-activities/ears-1

[^1_53]: https://www.ssec.wisc.edu/meetings/cspp/2013/presentations/NPP_Users_Meeting_2013.pdf

[^1_54]: https://imos.org.au/facility/satellite-remote-sensing/sea-surface-temperature-products

[^1_55]: https://cgms-info.org/html/IWW10_PROC/groups/cps/documents/document/pdf_conf_p56_s5_01_key_v.pdf

[^1_56]: https://pmc.ncbi.nlm.nih.gov/articles/PMC10869837/

[^1_57]: https://www.sciencedirect.com/science/article/abs/pii/S0034425713001235

[^1_58]: https://imos.org.au/wp-content/uploads/2024/07/Paltoglou_2010_IMOS_AVHRR_v1_0.pdf

[^1_59]: https://en.wikipedia.org/wiki/Davis_Station

[^1_60]: https://www.antarctica.gov.au/antarctic-operations/stations-and-field-locations/davis/

[^1_61]: https://www.antarctica.gov.au/antarctic-operations/stations-and-field-locations/casey/

[^1_62]: https://www.spaceacademy.net.au/spacelink/auspacecom.htm

[^1_63]: https://researchdata.edu.au/station-footprint-casey-davis-mawson/701785

[^1_64]: https://www.bom.gov.au/climate/how/newproducts/images/gcos2001.pdf

[^1_65]: https://www.instagram.com/reel/DEwM0SYu9Qz/

[^1_66]: https://dev.magda.io/dataset/ds-dga-1d5ce743-eb67-4136-bdf0-144044772194

[^1_67]: https://www.tern.org.au/news/workshops-bring-remote-sensing-down-to-earth/

[^1_68]: https://imos.org.au/news/category/satellite-remote-sensing

[^1_69]: https://www.ga.gov.au/bigobj/GA19990.pdf

[^1_70]: https://earth.esa.int/eogateway/documents/20142/37627/ERS-1-Mission-Announcement-of-Opportunity.pdf

[^1_71]: https://www.bom.gov.au/resources/learn-and-explore/radar-and-equipment-knowledge-centre/satellites

[^1_72]: https://www.angstt.gov.au/about/annual-reports/annual_report_2001.pdf

[^1_73]: https://www.utas.edu.au/physics/space-tracking

[^1_74]: https://www.perthwalkabout.com/Places-of-Interest/murdoch-university.html

[^1_75]: https://www.angstt.gov.au/__data/assets/pdf_file/0014/112703/annual_report_2014.pdf

[^1_76]: https://ucc.edu.au/murdoch-university

[^1_77]: https://www.iac2025.org/partner/unsw-canberra-space/

[^1_78]: https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0100762

[^1_79]: https://pubs.ssec.wisc.edu/research_Resources/publications/pdfs/SSECPUBS/SSEC_Publication_No_04_12_K1.pdf

[^1_80]: https://greens.org.au/wa/news/eyes-sky

[^1_81]: https://wmo.int/events/7th-dbnet-coordination-group-meeting-19-21-march-2024

[^1_82]: https://community.wmo.int/events/7th-dbnet-coordination-group-meeting-19-21-march-2024

[^1_83]: https://nwp-saf.eumetsat.int/monitoring/ears_mon/DBNet_station_status.html

[^1_84]: https://www.bom.gov.au/sites/default/files/2026-02/mission-requirements-australian-microwave-satellite-sounding-instrument-brr-119.pdf

[^1_85]: https://www.data.jma.go.jp/mscweb/en/DBNet/DBNet.html

[^1_86]: https://www.unsw.edu.au/content/dam/pdfs/unsw-canberra/space/2023-04-research/2023-04-Australian_Bureau_of_Meteorology_Pre-Phase_A_Mission_Study_Report_0.pdf

[^1_87]: https://wmo.int/dbnet-implementation-status

[^1_88]: http://www.cgms-info.org/wp-content/uploads/2021/10/CGMS-43_WG_I_report.pdf

[^1_89]: https://www.cgms-info.org/wp-content/uploads/2021/10/CGMS-48_report.pdf

[^1_90]: https://nwp-saf.eumetsat.int/downloads/dbnet/timeliness/

[^1_91]: https://old.wmo.int/wiswiki/tiki-download_file.php%3FfileId=3274

[^1_92]: https://nsidc.org/data/viirs

[^1_93]: https://registry.opendata.aws

[^1_94]: https://www.cfat.org.au/cfat-se

[^1_95]: https://svs.gsfc.nasa.gov/30693/

[^1_96]: https://www.nasa.gov/smallsat-institute/sst-soa/ground-data-systems-and-mission-operations/

[^1_97]: https://www.bis.doc.gov/index.php/documents/other-areas/617-space-survey-pdf/file

[^1_98]: https://www.ga.gov.au/dea-archived/news/DEA-Program-Roadmap-May-2020.pdf

[^1_99]: https://www.naturalhazards.com.au/crc-collection/downloads/active_fire_detection_using_the_himawari-8_satellite_final_project_report.pdf

[^1_100]: http://www.virtuallab.bom.gov.au/files/9313/8119/0983/4th_AOMSUC_Abstracts_-_FINAL.pdf

[^1_101]: https://oceancurrent.aodn.org.au/timeseries/whatsshown.htm

[^1_102]: https://www.sciencedirect.com/science/article/abs/pii/S0169809516300382

[^1_103]: https://pmc.ncbi.nlm.nih.gov/articles/PMC6559264/

[^1_104]: https://rmets.onlinelibrary.wiley.com/doi/10.1002/qj.70045

[^1_105]: https://imos.org.au/data/ocean-information-resources

