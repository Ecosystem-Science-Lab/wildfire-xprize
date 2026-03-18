# Alice Springs Ground Station Research

Last updated: 2026-03-17

## 1. Facility Overview

### Official Names and History

The facility has gone through several naming conventions:

- **Current official name:** Alice Springs Satellite Ground Station (or simply "Alice Springs Ground Station")
- **USGS station code:** ASN
- **Historical name:** Australian Landsat Station (1979-1986), then Australian Centre for Remote Sensing (ACRES, 1986-2001)
- The National Earth Observation Group (NEOG) succeeded ACRES when Geoscience Australia was formed in 2001

GA operates two complementary facilities:
- **Data Acquisition Facility (DAF)** -- Alice Springs (satellite downlink)
- **Data Processing Facility (DPF)** -- Canberra, Symonston ACT (archiving and processing)

### Operator

**Geoscience Australia (GA)**, an Australian Government agency within the Department of Industry, Science and Resources.

The facility sits under GA's **Space Division**, led by Chief of Division **Alison Rose**. The most relevant branch is **Satellite Land Imaging Collection (SLIC)**, headed by **Dr David Hudson** (Director, Satellite Programs). Hudson is also the founding chair of ANGSTT and former Co-Chair Asia Oceania at the Group on Earth Observations (GEO). His PhD is from ANU.

### Location

Coordinates: 23.7589 S, 133.8822 E (Alice Springs, Northern Territory)

GA has been studying **relocation** of the ground station within the Alice Springs region to address urban encroachment and gain more real estate for additional antennas and co-located calibration/validation infrastructure.

## 2. Infrastructure

### GA Antennas at Alice Springs

| Antenna ID | Size | Manufacturer | Bands | Notes |
|-----------|------|-------------|-------|-------|
| ASP1 | 9m | Datron | X-band | Primary Landsat antenna |
| ASP2 | 9m | ViaSat | X-band | Upgraded ~2016 ($4M AUD upgrade) |
| ASP3 | 2.4m | ESS | S-band? | Smaller missions |
| ASP4 | 3m | Orbital | Various | Added later |

### CfAT/Viasat Real-Time Earth Antennas (Separate Facility)

Located at CfAT's Heath Road site in Alice Springs (not the GA facility):

| Antenna | Size | Manufacturer | Bands | Notes |
|---------|------|-------------|-------|-------|
| RTE-1 | 7.3m | Viasat | L/S/X/Ka | Full motion |
| RTE-2 | 7.3m | Viasat | L/S/X/Ka | Full motion |

Payload downlink rates: 15 Mbps to 6,400 Mbps (X and Ka bands). Supports LEO, MEO, and GEO missions.

### Network Connectivity

- GA Alice Springs to GA Canberra: **optic fibre link** (dedicated)
- CfAT Space Precinct: **1 Gbps optical fibre** connectivity
- CfAT also has 300 kV transformer capacity

## 3. Satellites Received at Alice Springs (GA Facility)

GA's Alice Springs station performs daily data downlinks from:

| Mission | Instrument | Type | Key Use |
|---------|-----------|------|---------|
| Landsat 8 | OLI/TIRS | Polar LEO | Land imaging (30m), thermal (100m) |
| Landsat 9 | OLI-2/TIRS-2 | Polar LEO | Land imaging (30m), thermal (100m) |
| Terra | MODIS | Polar LEO | Fire detection, land/ocean/atmosphere |
| Aqua | MODIS | Polar LEO | Fire detection, land/ocean/atmosphere |
| Suomi NPP | VIIRS | Polar LEO | Fire detection (375m), environmental |
| NOAA-20 | VIIRS | Polar LEO | Fire detection (375m) |
| NOAA-21 | VIIRS | Polar LEO | Fire detection (375m) |
| Sentinel-2A/2B | MSI | Polar LEO | Land imaging (10-60m) via Copernicus |
| NOAA (various) | AVHRR | Polar LEO | Weather, fire detection (discontinued from Hotspots June 2025) |

**Coverage:** Entire Australian landmass, most of Papua New Guinea, and Eastern Indonesia.

**Note:** Himawari-9 (AHI) is a geostationary satellite -- it broadcasts continuously and is received by the **Bureau of Meteorology** at their own ground stations (Perth, Melbourne, Darwin), not by GA at Alice Springs.

## 4. Data Flow Architecture

### Landsat Data Flow

```
Landsat 8/9 satellite
    |
    v (X-band downlink during overpass)
Alice Springs Ground Station (DAF)
    |
    v (optic fibre link)
Canberra Data Processing Facility (DPF)
    |
    v (network transfer)
USGS EROS Center, Sioux Falls SD (DPAS)
    |
    v (Level 1/2 processing)
USGS EarthExplorer / Landsat collections
```

**Current latency for processed Landsat over Australia: 4-6 hours minimum** (often longer). This is the pipeline we want to short-circuit.

### DEA Hotspots Data Flow

```
Polar satellites (MODIS on Aqua, VIIRS on NPP/NOAA-20/21)
    |
    v (direct broadcast X-band downlink)
Alice Springs Ground Station
    |
    v (produces Level 0 datasets: MODIS L0, VIIRS RDR, NOAA HDF)
    v (transfer via network to Canberra, then AWS)
Canberra Processing → AWS
    |
    v (fire detection algorithms: MOD14, AFIMG, BRIGHT_AHI, AFMOD)
DEA Hotspots database
    |
    v (published via web, WMS, WFS, GeoJSON, KML)
https://hotspots.dea.ga.gov.au/
```

Additionally, Himawari-9 AHI data flows separately through BoM:

```
Himawari-9 (geostationary, every 10 min)
    |
    v (received by BoM ground stations)
BoM processing
    |
    v (BRIGHT_AHI algorithm)
DEA Hotspots
```

### DEA Hotspots Latency

- **Best case: 17 minutes** from satellite pass to published hotspot
- **Typical MODIS: ~30 minutes** after Aqua/Terra overpass
- **Typical Himawari AHI: ~20 minutes** after observation
- **Geostationary updates: every 10 minutes** (but with processing delay)
- **Polar orbiting: 2-10 updates per day** for any given location
- **Sunrise/sunset periods** (+/- 1 hour) are considered unreliable

**Critical limitation stated by GA:** "DEA Hotspots is not published in real time and should not be used for safety of life decisions."

## 5. Australia's Investment in Ground Station Modernization

### Landsat Next Partnership ($207.4M AUD)

Announced February 2024, formally signed by USGS Director David Applegate and Australian Minister for Resources Madeleine King.

**Australia's commitment:** $207.4 million AUD over four years and ongoing funding:
- Enhancing satellite ground station facilities at Alice Springs
- Advanced new data processing and analytics capabilities
- Personnel, services, and science in support of Landsat Next

**In exchange, Australia receives:**
- Free, streamlined, prioritised, and open access to Landsat Next data
- Partnership in the Landsat 2030 International Partnership Initiative

**Landsat Next specs:**
- Three satellites operating in tandem
- 26-band superspectral capability
- Higher resolution and greater frequency than current Landsat
- **Planned launch: early 2030s (targeting 2031)**

**What GA provides under the partnership:**
- Ground station support for current and future Landsat satellites
- Land imaging data processing, QA, and distribution covering **one third of the Earth**
- New science and technology to help users take full advantage of Landsat Next

### Planned Procurements (2024-2025)

From AusTender records:
- "Design and construction partner for Alice Springs satellite ground station" (Q1 2024/2025)
- "International Forest Initiative (IFCI) X-band Antenna aka ViaSat 9m" (Q1 2024/2025)

This suggests active construction/upgrade work at Alice Springs during 2025-2026 -- potentially relevant timing for our April 2026 competition window.

## 6. CfAT/Viasat Real-Time Earth at Alice Springs

### Separate from GA facility

The CfAT Space Precinct is a **different facility** from GA's ground station, located at CfAT's Heath Road site.

### Key Details

- **Owner:** CfAT Satellite Enterprises Pty Ltd (CfATSE) -- a wholly-owned commercial subsidiary of Centre for Appropriate Technology Ltd
- **Operator/OEM:** Viasat, Inc. (facility is leased to Viasat)
- **Status:** Australia's first and only Aboriginal-owned-and-operated ground segment service provider
- **Opened:** June 2020
- **Financed by:** Indigenous Business Australia (IBA)

### Service Model

Viasat's Real-Time Earth provides **Ground-Station-as-a-Service (GSaaS)**:
- Pay-per-use model
- Automated scheduling
- Real-time streaming to customer's endpoint of choice
- Supports command uplink and data downlink
- Turn-key satellite-to-ground communications

### Contact

- **CfAT Satellite Enterprises:** cfatse@cfat.org.au, phone (08) 8959 6100
- **Address:** 475 South Stuart Highway, Alice Springs NT 0873
- **Viasat RTE Services:** RTEservices@viasat.com

### Relevance to Our Project

This is potentially **very interesting** as an alternative to working through GA:
- GSaaS model means we could potentially purchase antenna time directly
- X-band capable antennas could downlink VIIRS, MODIS, or even Landsat data
- Pay-per-use means no lengthy MOU process
- 7.3m antennas with full-motion tracking
- However: we'd need our own processing software (CSPP for VIIRS/MODIS, FarEarth for Landsat)
- **Question:** Can CfAT/Viasat receive direct broadcast from VIIRS/MODIS polar orbiters on demand? This is the critical question to ask.

### Site Characteristics

- Over 250 cloud-free days per year
- Low light pollution (SQM > 20)
- Clear line of sight to 10 degrees above horizon
- Stable atmospheric conditions

## 7. How NAU Could Approach GA About a Research Partnership

### Organizational Entry Points

**Primary contact for earth observation inquiries:**
- **Email:** earth.observation@ga.gov.au
- **General inquiries:** clientservices@ga.gov.au, 1800 800 173
- **Switchboard:** +61 2 6249 9111

**Key people to target:**
- **Alison Rose** -- Chief of Space Division (overall decision-maker)
- **Dr David Hudson** -- Director, Satellite Programs, SLIC Branch (runs Alice Springs/Landsat operations; founding chair of ANGSTT; PhD from ANU; most technically relevant contact)
- **Leyla Alpaslan** -- Head, Digital Earth (oversees DEA platform including Hotspots)

**Physical address:**
Geoscience Australia, Cnr Jerrabomberra Ave and Hindmarsh Drive, Symonston ACT 2609, Australia
GPO Box 378, Canberra ACT 2601

### Partnership Approach Strategy

**1. Lead with the US-Australia relationship angle:**
- GA's entire ground station existence is built on the US-Australia Landsat partnership (since 1979)
- NAU is a US university -- this fits the bilateral cooperation narrative
- USGS EROS is a natural connector (they have working relationships with both NAU's remote sensing community and GA)
- The $207M Landsat Next investment means GA is actively looking to demonstrate the value of Australian ground station infrastructure

**2. Frame as a demonstration project:**
- "Demonstrate real-time fire detection capability using Australian ground station infrastructure"
- Aligns with GA's stated mission: earth observation data for "responding to natural disasters such as bushfires"
- Aligns with the Landsat Next partnership's emphasis on "new science and technology"
- 2-week window minimizes risk/commitment for GA

**3. Leverage existing frameworks:**
- GA already has extensive collaboration with USGS -- NAU can position itself as an extension of this relationship
- The Australian Research Council (ARC) supports international research collaboration through eligible Australian institutions
- Earth Observation Australia (EOA) is the independent community organization (570 members) that could provide introductions
- ANGSTT coordinates across Australian ground segment operators -- David Hudson founded it

**4. Practical ask (keep it small):**
- Access to the data stream at one point in the Alice Springs-to-Canberra pipeline
- Permission to run real-time processing software (FarEarth Observer or equivalent)
- Only for a 2-week window in April 2026
- No hardware deployment required at their facility
- Offer joint publication and XPRIZE visibility

### Australian University Partners as Intermediaries

Rather than approaching GA cold, partner with an Australian university first:
- **ANU (Canberra)** -- geographically close to GA, strong research relationship, could co-sponsor the approach
- **UNSW Canberra** -- space engineering, ground station expertise
- **University of Tasmania** -- already collaborates with GA on VLBI/geodetic work
- A joint NAU-Australian-university approach to GA is far more credible than NAU alone

## 8. Existing Academic Partnership Frameworks

### GA's Current Academic Collaborations

- **University of Tasmania:** Joint operation of VLBI stations, Australian VLBI Correlation Centre at ANU's National Computational Infrastructure
- **AuScope:** Geospatial framework collaboration
- **AARNet:** Optic fibre connections to geodetic observatories (Katherine, Yarragadee -- precedent for network infrastructure partnerships)

### Broader Frameworks

- **Group on Earth Observations (GEO):** Australia is a member; GA participates actively
- **CEOS (Committee on Earth Observation Satellites):** GA participates in WGISS and other working groups
- **Earth Observation Australia (EOA):** Independent community organization
  - 570 members (research, government, industry, NFP)
  - Contact: communications@eoa.org.au
  - Based at University of Queensland, Saint Lucia QLD 4072
  - Hosts the Earth Observation Governance Network (EOGN) workshops
  - **Advancing Earth Observation Forum:** November 9-12, 2026
  - EOA explicitly promotes fire detection innovation and references the XPRIZE competition
- **CSIRO Centre for Earth Observation:** International engagement role, works with GA and BoM
- **SmartSat CRC:** Cooperative Research Centre for space -- Alison Rose has presented at their events

### What's Missing

There is **no standard "apply for a research partnership" process** at GA. It's relationship-based. You need:
1. A warm introduction (via USGS, an Australian university, or EOA)
2. A specific, small ask
3. Alignment with GA's stated priorities (bushfire response, demonstrating ground station value)

## 9. DEA Hotspots -- Relationship to Alice Springs

### Direct Connection

DEA Hotspots is **directly fed by Alice Springs ground station data.** The confirmed pipeline:

1. Polar-orbiting satellites (Aqua/MODIS, Suomi NPP/VIIRS, NOAA-20/VIIRS, NOAA-21/VIIRS) broadcast data as they overpass Australia
2. Alice Springs ground station receives the direct broadcast (X-band)
3. Data is processed to Level 0 (MODIS L0, VIIRS Raw Data Records, NOAA HDF files)
4. Datasets transfer via network link to Canberra, then to AWS for further processing
5. Fire detection algorithms run (MOD14 for MODIS, AFIMG for VIIRS, BRIGHT_AHI for Himawari)
6. Results published to DEA Hotspots

**Himawari-9 AHI data follows a separate path** through BoM's ground stations (not Alice Springs), but also feeds into DEA Hotspots.

### Current Satellites Feeding DEA Hotspots (as of early 2026)

| Satellite | Sensor | Status |
|-----------|--------|--------|
| Aqua | MODIS | Active |
| Terra | MODIS | **Unavailable** (power problems since May 2024; direct broadcast stopped) |
| Suomi NPP | VIIRS | Active |
| NOAA-20 | VIIRS | Active |
| NOAA-21 | VIIRS | Active |
| Himawari-9 | AHI | Active (via BoM) |
| NOAA-19 | AVHRR | **Discontinued** from Hotspots June 2025 |

### DEA Hotspots Data Access

- **Public portal:** https://hotspots.dea.ga.gov.au/
- **Secure portal (emergency managers):** https://hotspots.dea.ga.gov.au/login
- **WMS/WFS web services** available
- **GeoJSON and KML feeds** (last 3 days)
- **AWS file access:** https://hotspots.dea.ga.gov.au/files
- **API endpoints** via WFS for programmatic access

### Implication for Our Project

DEA Hotspots proves that GA already processes VIIRS and MODIS data from Alice Springs for fire detection. The algorithms are running. The question is whether we can get the detections **faster** than the current 17-30 minute pipeline -- either by:
1. Tapping into the data stream before it enters the full DEA Hotspots pipeline
2. Running our own processing in parallel on the same raw data
3. Getting DEA Hotspots to push alerts to us as soon as they're generated (before web publication delay)

## 10. Contact Pathways -- Summary

### Geoscience Australia (Primary Target)

| Contact | Email | Role |
|---------|-------|------|
| Earth Observation inquiries | earth.observation@ga.gov.au | General EO queries |
| Client services | clientservices@ga.gov.au | General inquiries |
| Media | media@ga.gov.au | Press inquiries |
| Alison Rose | (via LinkedIn or GA switchboard) | Chief, Space Division |
| Dr David Hudson | (via LinkedIn or GA switchboard) | Director, Satellite Programs, SLIC |
| Leyla Alpaslan | (via LinkedIn or GA switchboard) | Head, Digital Earth |
| GA switchboard | +61 2 6249 9111 | Route to specific people |
| Toll-free | 1800 800 173 | General inquiries |

### CfAT / Viasat (Alternative Path)

| Contact | Email/Phone | Role |
|---------|-------------|------|
| CfAT Satellite Enterprises | cfatse@cfat.org.au | General Manager |
| CfAT Phone | (08) 8959 6100 | Alice Springs office |
| Viasat RTE Services | RTEservices@viasat.com | Ground Station as a Service |

### Community / Intermediary Organizations

| Organization | Contact | Notes |
|-------------|---------|-------|
| Earth Observation Australia (EOA) | communications@eoa.org.au | 570-member community org, UQ-based |
| ANGSTT | (via GA) | David Hudson founded it |
| SmartSat CRC | (via web) | Cooperative Research Centre for space |
| CSIRO Centre for Earth Observation | (via CSIRO web) | International engagement |

### USGS (Warm Introduction Path)

Since GA's entire Alice Springs operation exists to support the Landsat partnership, USGS contacts could provide warm introductions:
- USGS EROS Center (Sioux Falls) has direct working relationship with GA Alice Springs
- USGS Landsat program office at Goddard Space Flight Center sends commands via Alice Springs
- NAU's existing USGS connections (if any) are the most natural bridge

## 11. Recommended Next Steps

### Immediate (This Week)

1. **Email earth.observation@ga.gov.au** with a concise inquiry about research collaboration for real-time fire detection, referencing the XPRIZE competition and NAU's university status
2. **Email CfAT Satellite Enterprises (cfatse@cfat.org.au)** to inquire about GSaaS pricing and capability for VIIRS/MODIS direct broadcast reception during April 2026
3. **Email Viasat RTE (RTEservices@viasat.com)** with the same inquiry -- they manage the commercial side

### Short-term (Next 2 Weeks)

4. **Contact Dr David Hudson** via LinkedIn -- he's the most technically relevant person at GA, runs the SLIC branch, founded ANGSTT, and would understand the value proposition immediately
5. **Contact EOA (communications@eoa.org.au)** to ask for introductions to the Australian fire detection / EO community
6. **Identify an Australian university partner** (ANU or UNSW Canberra preferred) to co-sponsor the GA approach

### Key Questions to Answer

- Can CfAT/Viasat RTE receive VIIRS direct broadcast on demand? What does it cost per pass?
- Is the GA Alice Springs-to-Canberra fibre link accessible for a research tap?
- Could we run CSPP (Community Satellite Processing Package) on VIIRS data at Alice Springs or Canberra?
- Does GA's current pipeline already produce VIIRS fire products faster than 17 minutes internally, with the Hotspots publication adding the delay?
- Is the Landsat X-band data stream at Alice Springs accessible before it ships to EROS?

---

## Sources

- [GA: Our Satellite and Ground Station Network](https://www.ga.gov.au/scientific-topics/space/our-satellite-and-ground-station-network)
- [USGS: Celebrating 40 Years of Landsat at Alice Springs](https://www.usgs.gov/landsat-missions/november-15-2019-celebrating-40-years-landsat-alice-springs-ground-station)
- [USGS: Alice Springs (ASN) Landsat Ground Station](https://landsat.usgs.gov/ASN)
- [GA: U.S.-Australia Landsat Next Partnership](https://www.ga.gov.au/scientific-topics/space/us-australia-landsat-next-partnership)
- [USGS: Australia Formally Partners for Landsat Next](https://www.usgs.gov/news/featured-story/usgs-and-australia-formally-partner-upcoming-landsat-next-satellite-mission)
- [The Conversation: Australia's $207M Satellite Commitment](https://theconversation.com/australia-just-committed-207-million-to-a-major-satellite-program-what-is-it-and-why-do-we-need-it-226621)
- [GA: DEA Hotspots](https://www.ga.gov.au/scientific-topics/dea/dea-data-and-products/dea-hotspots)
- [DEA Hotspots Knowledge Hub](https://knowledge.dea.ga.gov.au/data/product/dea-hotspots/index.html)
- [DEA Hotspots Portal](https://hotspots.dea.ga.gov.au/)
- [Viasat: Real-Time Earth Ground Station in Australia](https://www.viasat.com/news/latest-news/government/2020/viasats-real-time-earth-ground-station-now-open-in-australia/)
- [Viasat: Real-Time Earth Service](https://www.viasat.com/government/antenna-systems/real-time-earth/)
- [CfAT Satellite Enterprises](https://www.cfat.org.au/cfat-se)
- [Viasat-CfAT Partnership Announcement](https://investors.viasat.com/news-releases/news-release-details/viasat-partners-centre-appropriate-technology-ltd-and-indigenous)
- [NT Space Infrastructure Overview](https://dtbar.nt.gov.au/industries/space-industry/overview-of-the-territory-space-infrastructure)
- [ANGSTT Network](https://www.angstt.gov.au/network)
- [GA: Organizational Structure](https://www.ga.gov.au/about/organisational-structure)
- [GA Space Division Directory](https://www.directory.gov.au/portfolios/industry-science-and-resources/geoscience-australia/space-division)
- [SLIC Branch Directory](https://www.directory.gov.au/portfolios/industry-science-and-resources/geoscience-australia/space-division/satellite-land-imaging-collection)
- [GA: Earth Observation from Space](https://www.ga.gov.au/scientific-topics/earth-observation)
- [IMOS Ground Stations](https://imos.org.au/facility/satellite-remote-sensing/ground-stations)
- [Earth Observation Australia](https://www.eoa.org.au/)
- [Australian Space Agency: Emergency Services and Space](https://www.space.gov.au/Australian-emergency-services-rely-on-space)
- [GA: 40 Years of Landsat in Australia](https://www.ga.gov.au/news/40-years-of-landsat-in-australia)
- [GA: DEA Contact Us](https://www.ga.gov.au/scientific-topics/dea/contact-us)
