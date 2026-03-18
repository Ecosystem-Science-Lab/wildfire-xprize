# Sequential and Temporal Fire Detection from Geostationary Satellite Data

Reference document covering diurnal temperature cycle modeling, sequential change-point
detection methods (CUSUM, SPRT, Bayesian), and their application to detecting small fires
through temporal integration of geostationary satellite observations.

Context: Himawari-8/9 AHI, 10-minute cadence, 2 km pixels over NSW Australia.
This is a confidence-building mechanism for the "refine" stage of a trigger-refine-confirm
pipeline, not early detection per se.

---

## 1. Overview and Rationale

### 1.1 The Problem

Individual geostationary frames may not detect small fires (50-500 m^2) because the
per-pixel brightness temperature (BT) increase is below or near the single-frame noise
floor. For a 2 km pixel (4 km^2 = 4 x 10^6 m^2), a 100 m^2 fire at 800 K produces a
pixel-integrated BT increase at 3.9 um of roughly 0.05-0.2 K (see sub_pixel_physics.md
for the derivation). This is comparable to or below the combined noise floor from:

- Detector noise (NEdT): <= 0.16 K at 300 K for AHI Band 7 (3.9 um)
- Atmospheric variability: ~0.2-0.5 K from water vapor fluctuations
- DTC model residuals: ~0.3-1.0 K depending on model quality

### 1.2 The Key Insight

A fire is a persistent positive anomaly. Noise is zero-mean. By modeling the expected
per-pixel BT (the diurnal temperature cycle plus atmospheric effects) and examining the
residuals across multiple consecutive frames, we can detect fires that are invisible in
any single frame. The signal grows linearly with integration time while noise grows as
sqrt(N), giving an SNR improvement of sqrt(N) for N frames.

For a 0.1 K signal in 0.3 K noise (SNR = 0.33 per frame):
- After 1 frame:  SNR = 0.33  (undetectable)
- After 9 frames: SNR = 1.0   (marginal)
- After 36 frames (6 hours): SNR = 2.0 (detectable with ~95% confidence)

This is where sequential detection theory provides the optimal framework.

### 1.3 Pipeline Position

```
TRIGGER (LEO/alert)  -->  REFINE (temporal integration)  -->  CONFIRM (next LEO pass)
                           ^^^^^^^^^^^^^^^^^^^^^^^^^
                           THIS DOCUMENT
```

The temporal integration stage takes a candidate pixel flagged by an initial trigger
(or routine scan) and applies sequential statistical tests to the time series of BT
residuals (observed minus predicted) to build confidence that a persistent thermal
anomaly exists.

---

## 2. Diurnal Temperature Cycle (DTC) Modeling

The foundation of temporal fire detection is an accurate model of expected (non-fire)
brightness temperature for each pixel at each time step. The fire signal is the residual
after subtracting this expected value.

### 2.1 The Gottsche-Olesen DTC Model

The standard physics-based DTC model (Gottsche and Olesen, 2001, 2009) uses a piecewise
function combining a cosine term (solar heating) and an exponential decay (radiative
cooling):

```
         ┌ T0 + Ta * cos(pi * (t - tm) / omega)                   for ts_rise <= t <= ts
T(t) =   │
         └ T0 + delta_T + [Ta*cos(pi*(ts-tm)/omega) - delta_T]
                          * exp(-(t - ts) / tau)                   for t > ts
```

Parameters (6 free parameters in GOT09):
- T0:      residual temperature near sunrise (K)
- Ta:      diurnal temperature amplitude (K)
- tm:      time of maximum temperature (hours, solar time)
- omega:   half-period of the cosine term (hours) — controls width of daytime warming
- ts:      time when free attenuation begins (hours) — transition to nighttime cooling
- delta_T: residual temperature difference (T_sunset_residual - T0)
- tau:     exponential decay time constant (hours)

Typical values for Australian savanna/woodland:
- Ta:    10-25 K (thermal IR), 5-15 K (MWIR 3.9 um due to reflected solar component)
- tm:    ~13:00-14:00 local solar time
- omega: ~7-8 hours
- ts:    ~15:00-17:00 local solar time
- tau:   ~3-6 hours

Reported accuracy:
- RMSE of ~0.5 K for the full diurnal cycle (GOT09, validated against in-situ)
- Best models achieve ~0.4 K RMSE for limited time periods
- Residual sigma after fitting: typically 0.3-0.8 K depending on conditions

### 2.2 Harmonic (Fourier) DTC Model

A simpler alternative using harmonic decomposition:

```
T(t) = T_mean + sum_{k=1}^{K} [a_k * cos(k * omega_0 * t) + b_k * sin(k * omega_0 * t)]
```

where omega_0 = 2*pi/24 (diurnal frequency in rad/hr) and K = 2-4 harmonics.

For K=2 (4 free parameters plus mean):

```
T(t) = T_mean + a1*cos(omega_0*t) + b1*sin(omega_0*t)
              + a2*cos(2*omega_0*t) + b2*sin(2*omega_0*t)
```

Advantages:
- Linear least squares fit (fast, robust)
- No need for initial parameter guesses
- Handles irregular sampling naturally

Disadvantages:
- Poorer representation of the sharp sunrise transition
- Typically ~0.5-1.0 K RMSE (worse than GOT09)
- May produce unphysical oscillations during nighttime

### 2.3 Kalman Filter DTC Model (Roberts & Wooster 2014)

The most relevant approach for our application. Roberts & Wooster (2014) developed
the Kalman Filter Algorithm (KFA) specifically for geostationary fire detection using
MSG-SEVIRI data.

#### Approach

1. Build a library of "basis DTCs" — representative diurnal temperature profiles for
   different surface types/seasons, derived from cloud-free historical observations.

2. For each pixel, use a robust matching algorithm to select the best-fitting basis DTC
   from the library.

3. Apply a Kalman filter to blend the basis DTC prediction with actual observations
   during confirmed cloud-free, fire-free periods.

4. The Kalman filter state estimate provides the expected background BT at each time step.
   The difference between observation and prediction is the innovation (residual).

#### Kalman Filter Equations

State space model for pixel brightness temperature:

```
State equation:     x[k] = F * x[k-1] + w[k]     w ~ N(0, Q)
Observation eqn:    z[k] = H * x[k] + v[k]        v ~ N(0, R)
```

where:
- x[k] = state vector (e.g., [T_background, dT/dt] or DTC parameters)
- F    = state transition matrix (encodes DTC evolution)
- Q    = process noise covariance (models uncertainty in DTC prediction)
- z[k] = observed BT at time k
- H    = observation matrix (maps state to observable)
- R    = observation noise covariance (NEdT^2 + atmospheric variability)

Prediction step:
```
x_pred[k]  = F * x_est[k-1]
P_pred[k]  = F * P_est[k-1] * F^T + Q
```

Update step (when observation available and cloud-free):
```
innovation[k] = z[k] - H * x_pred[k]
S[k]          = H * P_pred[k] * H^T + R       (innovation covariance)
K[k]          = P_pred[k] * H^T * S[k]^{-1}   (Kalman gain)
x_est[k]      = x_pred[k] + K[k] * innovation[k]
P_est[k]      = (I - K[k] * H) * P_pred[k]
```

When observation is missing (cloud gap):
```
x_est[k] = x_pred[k]     (use prediction only)
P_est[k] = P_pred[k]     (uncertainty grows)
```

#### Key Results from Roberts & Wooster 2014

- Background RMSD: 0.2 K reduction compared to non-KF approach (the KFA provides
  more accurate background estimates)
- Detection improvement: KFA detects up to ~80% more fire pixels at the peak of the
  diurnal fire cycle compared to the existing pFTA algorithm
- Trade-off: doubled false alarm rate compared to pFTA (more sensitive but less specific)
- Limitation: computationally costly; requires full diurnal variation before detection
  (not suited to real-time product generation in original form)

### 2.4 Broad Area Training (BAT) Method

Used in the multi-temporal FTA algorithm for next-generation geostationary data:

1. Aggregate cloud-free median BT from a broad area sharing the same latitude band
   and similar land cover.
2. Stack temporally using local solar time to build a standardized diurnal template.
3. Fit the template to individual pixel observations using weighted least squares,
   halving the weight of negative residuals (to resist cloud contamination pulling
   the fit down).
4. The fitted curve provides expected background BT for anomaly detection.

Detection: threshold applied to (observed - fitted) difference. Detects positive thermal
anomalies in up to 99% of cases where fires are also detected by LEO fire products.

### 2.5 RST (Robust Satellite Technique) Approach

The RST-FIRES algorithm (Filizzola et al., 2017) uses a statistical anomaly index
called ALICE (Absolute Local Index of Change of the Environment):

```
ALICE(x, y, t) = [V(x,y,t) - mu_V(x,y)] / sigma_V(x,y)
```

where:
- V(x,y,t)      = observed signal (BT or BT difference) at pixel (x,y), time t
- mu_V(x,y)     = temporal mean of V at pixel (x,y) from multi-year archive
- sigma_V(x,y)  = temporal standard deviation of V at pixel (x,y)

Fire detected when ALICE exceeds a threshold (typically 2-3 sigma).

Key advantage: purely data-driven, no physical DTC model needed, exportable across
sensors and regions. Reported to be 3 to 70 times more sensitive than other SEVIRI-based
fire products.

### 2.6 Practical Considerations for Background Modeling

**Cloud gaps**: The 10-minute cadence of Himawari means ~144 observations per day per
pixel. Cloud cover in NSW during fire season (October-March) typically allows 50-100
clear observations per day. Short cloud gaps (< 4 hours) can be interpolated by the
DTC model or Kalman filter prediction. Longer gaps degrade the background estimate
and increase uncertainty.

**Reflected solar contamination at 3.9 um**: During daytime, Band 7 (3.9 um) includes
significant reflected solar radiation. This adds a solar-zenith-angle-dependent component
to the diurnal cycle that must be modeled. The daytime 3.9 um signal has roughly equal
contributions from thermal emission and reflected solar at typical ground temperatures
(~300 K). At night, the signal is purely thermal, which simplifies the background model
but reduces sensitivity to fires (the 3.9 um channel loses its sensitivity advantage
over 11 um for fire-background discrimination when reflected solar is absent from
both channels).

**Surface property changes**: Post-fire changes in emissivity and albedo, vegetation
phenology, and soil moisture all affect the baseline BT. These evolve on timescales of
days to weeks and can be handled by:
- Adaptive Kalman filter with slowly varying process noise
- Rolling window recalibration of DTC parameters (7-30 day windows)
- Seasonal DTC libraries updated from recent clear-sky observations

---

## 3. Sequential Detection Methods

Given a time series of residuals r[k] = BT_observed[k] - BT_predicted[k], the question
is: when should we conclude that a persistent positive anomaly (fire) has begun?

### 3.1 Problem Formulation

**Pre-change (H0)**: r[k] ~ N(0, sigma^2)  (no fire; residuals are zero-mean noise)
**Post-change (H1)**: r[k] ~ N(mu, sigma^2)  (fire present; residuals have positive mean mu)

The change occurs at an unknown time nu. We want to detect the change as quickly as
possible while maintaining a low false alarm rate.

Key parameters:
- sigma:  residual standard deviation (~0.3-0.8 K after DTC subtraction)
- mu:     expected BT increase from fire (~0.05-0.5 K for small fires)
- SNR:    mu / sigma per frame (~0.1-1.0)

### 3.2 CUSUM (Cumulative Sum) Test

CUSUM is the workhorse of sequential change detection. It is minimax optimal: among
all tests with a given false alarm rate, CUSUM minimizes the worst-case expected
detection delay (Lorden 1971, Moustakides 1986).

#### One-Sided Upper CUSUM (detecting positive shift)

```
S[0] = 0
S[k] = max(0, S[k-1] + r[k] - k_ref)

Alarm when S[k] >= h
```

where:
- r[k]   = residual at time k (observed - predicted BT)
- k_ref  = reference value (allowance/slack)
- h      = decision threshold

The CUSUM statistic S[k] accumulates evidence for a positive shift. The max(0, ...)
operation resets the statistic when evidence goes negative, effectively forgetting
periods of no anomaly and focusing on the most recent evidence.

#### Parameter Selection

**Reference value k_ref**: Set to half the shift size we want to detect optimally:

```
k_ref = mu_1 / 2
```

where mu_1 is the minimum shift of interest. For detecting a 0.2 K fire signal:
k_ref = 0.1 K.

More precisely, from likelihood ratio theory:

```
k_ref = (mu_1 - mu_0) / 2 = mu_1 / 2    (since mu_0 = 0 under H0)
```

**Decision threshold h**: Controls the trade-off between detection delay and false alarm
rate. Larger h = fewer false alarms but longer delay.

The in-control Average Run Length (ARL_0, mean time to false alarm):

| k=0.5, h (in sigma units) | ARL_0 (frames) | ARL_0 (hours at 10min) |
|----------------------------|-----------------|------------------------|
| h = 4 sigma                | 336             | 56 hours               |
| h = 5 sigma                | 930             | 155 hours              |

Out-of-control ARL (mean detection delay) for k=0.5 (in sigma units):

| Mean Shift (sigma) | h=4, ARL_1 | h=5, ARL_1 | Shewhart ARL_1 |
|---------------------|------------|------------|----------------|
| 0.25                | 74.2       | 140        | 281.14         |
| 0.50                | 26.6       | 38.0       | 155.22         |
| 1.00                | 8.38       | 10.4       | 44.0           |
| 1.50                | 4.75       | 5.75       | 14.97          |
| 2.00                | 3.34       | 4.01       | 6.30           |

CUSUM is vastly superior to single-frame (Shewhart) detection for small shifts.
For a 0.5-sigma shift, CUSUM detects in ~27-38 frames vs ~155 for single-frame.

#### Asymptotic Detection Delay Formula

The expected detection delay (ADD) for CUSUM is approximately:

```
E[detection delay] ≈ h / D_KL(p1 || p0) + O(1)
```

or equivalently:

```
E[detection delay] ≈ log(ARL_0) / D_KL(p1 || p0)
```

where D_KL is the Kullback-Leibler divergence between post-change and pre-change
distributions. For Gaussian shift from N(0, sigma^2) to N(mu, sigma^2):

```
D_KL = mu^2 / (2 * sigma^2) = SNR^2 / 2
```

So for Gaussian CUSUM:

```
E[detection delay] ≈ 2 * log(ARL_0) / SNR^2
```

Example: For SNR = 0.5 per frame, ARL_0 = 1000 frames:
```
E[delay] ≈ 2 * log(1000) / 0.25 ≈ 2 * 6.9 / 0.25 ≈ 55 frames ≈ 9.2 hours
```

#### CUSUM Pseudocode for Fire Detection

```python
def cusum_fire_detector(residuals, k_ref, h, sigma):
    """
    Apply one-sided upper CUSUM to BT residual time series.

    Parameters:
        residuals: array of (observed_BT - predicted_BT) values
        k_ref:     reference value (K), typically mu_target / 2
        h:         decision threshold (K)
        sigma:     residual standard deviation (K), for normalization

    Returns:
        alarm_time: index of first alarm, or None
        cusum_values: array of CUSUM statistic values
    """
    S = 0.0
    cusum_values = []

    for k, r in enumerate(residuals):
        # Normalize residual
        z = r / sigma

        # Update CUSUM (using normalized values, so h and k_ref also in sigma units)
        S = max(0.0, S + z - k_ref)
        cusum_values.append(S)

        # Check for alarm
        if S >= h:
            return k, cusum_values

    return None, cusum_values
```

### 3.3 SPRT (Sequential Probability Ratio Test)

SPRT is optimal in the sense that it achieves the minimum expected sample size among
all tests with the same Type I and Type II error probabilities (Wald & Wolfowitz).

#### Formulation

For each observation r[k], compute the log-likelihood ratio:

```
Lambda[k] = sum_{i=1}^{k} log( p1(r[i]) / p0(r[i]) )
```

For Gaussian H0: r ~ N(0, sigma^2) vs H1: r ~ N(mu, sigma^2):

```
log( p1(r) / p0(r) ) = (mu * r / sigma^2) - (mu^2 / (2 * sigma^2))
                      = (mu / sigma^2) * (r - mu/2)
```

So the cumulative log-likelihood ratio is:

```
Lambda[k] = (mu / sigma^2) * sum_{i=1}^{k} (r[i] - mu/2)
           = (mu / sigma^2) * [sum(r[i]) - k * mu/2]
```

#### Decision Rule

```
If Lambda[k] >= log(A):  Declare H1 (fire detected)
If Lambda[k] <= log(B):  Declare H0 (no fire)
Otherwise:               Continue sampling
```

Stopping boundaries (Wald's approximation):
```
A = (1 - beta) / alpha       →  log(A) ≈ log((1-beta)/alpha)
B = beta / (1 - alpha)       →  log(B) ≈ log(beta/(1-alpha))
```

where:
- alpha = probability of false alarm (Type I error)
- beta  = probability of missed detection (Type II error)

Example: For alpha = 0.01, beta = 0.05:
```
log(A) = log(0.95/0.01) = log(95) = 4.55
log(B) = log(0.05/0.99) = log(0.0505) = -2.99
```

#### Expected Sample Size (Wald's Formula)

Under H0 (no fire):
```
E_0[N] ≈ [(1-alpha)*log(B) + alpha*log(A)] / E_0[log(p1/p0)]
        = [(1-alpha)*log(B) + alpha*log(A)] / (-mu^2/(2*sigma^2))
```

Under H1 (fire present):
```
E_1[N] ≈ [beta*log(B) + (1-beta)*log(A)] / E_1[log(p1/p0)]
        = [beta*log(B) + (1-beta)*log(A)] / (mu^2/(2*sigma^2))
```

For the Gaussian case, E_1[N] simplifies to approximately:

```
E_1[N] ≈ 2 * log((1-beta)/alpha) / SNR^2
```

Example: For SNR = 0.5, alpha = 0.01, beta = 0.05:
```
E_1[N] ≈ 2 * 4.55 / 0.25 ≈ 36 frames ≈ 6 hours
```

#### CUSUM vs SPRT Comparison

- SPRT: optimal for testing H0 vs H1 (binary hypothesis). Can declare "no fire" and
  stop. Requires specifying the alternative (mu under H1).
- CUSUM: optimal for change-point detection (the change time is unknown). Never declares
  "no fire" — continues monitoring. Minimax optimal against worst-case change point.

For our application, CUSUM is more natural because:
1. We are monitoring continuously, not testing a fixed hypothesis
2. The fire onset time is unknown
3. We want to detect fires of unknown size (CUSUM adapts via k_ref)

However, SPRT can be useful in a two-stage approach: CUSUM flags candidates, then SPRT
provides a formal accept/reject test on the flagged segment.

### 3.4 Bayesian Online Change-Point Detection (BOCPD)

Adams & MacKay (2007) developed an online algorithm that maintains a probability
distribution over the "run length" — the time since the last change point.

#### Core Equations

Let r_t be the run length at time t (time since last change point).

The joint distribution is updated recursively:

```
p(r_t, x_{1:t}) = sum_{r_{t-1}} pi_t * p(r_t | r_{t-1}) * p(r_{t-1}, x_{1:t-1})
```

where pi_t = p(x_t | r_{t-1}, x^(r)) is the predictive probability of the new
observation given the current run length.

**Growth probability** (run continues, r_t = r_{t-1} + 1):

```
p(r_t = ell, x_{1:t}) = p(r_{t-1} = ell-1, x_{1:t-1}) * pi_{t-1}^(ell) * (1 - H(r_{t-1}))
```

**Change-point probability** (run resets, r_t = 0):

```
p(r_t = 0, x_{1:t}) = sum_{r_{t-1}} p(r_{t-1}, x_{1:t-1}) * pi_{t-1}^(r) * H(r_{t-1})
```

where H(tau) is the hazard function (prior probability of change point):

```
H(tau) = p_gap(tau) / (1 - P_gap(tau))
```

For a constant hazard rate lambda (geometric prior on run length):
```
H(tau) = 1/lambda    (constant, e.g., 1/1000 for expected run of 1000 frames)
```

**Conjugate updates** (for exponential family models):

```
nu_t^(0) = nu_prior            (reset hyperparameters on change)
nu_t^(ell) = nu_{t-1}^(ell-1) + 1

chi_t^(0) = chi_prior
chi_t^(ell) = chi_{t-1}^(ell-1) + u(x_t)
```

where u(x_t) is the sufficient statistic of x_t.

**For Gaussian with unknown mean (known variance):**
```
Prior: mu ~ N(mu_0, sigma_0^2)
Posterior after ell observations: mu ~ N(mu_ell, sigma_ell^2)

mu_ell = (mu_0/sigma_0^2 + sum(x_i)/sigma_obs^2) / (1/sigma_0^2 + ell/sigma_obs^2)
sigma_ell^2 = 1 / (1/sigma_0^2 + ell/sigma_obs^2)

Predictive: x_{t+1} | run_length=ell ~ N(mu_ell, sigma_obs^2 + sigma_ell^2)
```

#### Pseudocode

```python
def bocpd_fire_detector(residuals, hazard_rate, mu_prior, sigma_prior, sigma_obs):
    """
    Bayesian Online Change-Point Detection for fire detection.

    Parameters:
        residuals:    array of BT residuals
        hazard_rate:  1/expected_run_length (e.g., 1/1000)
        mu_prior:     prior mean of residuals under no-fire (0.0)
        sigma_prior:  prior std of mean estimate
        sigma_obs:    observation noise std

    Returns:
        changepoint_probs: probability of change point at each time
        run_length_dist:   run length distribution over time
    """
    T = len(residuals)
    # Run length distribution: R[t, ell] = p(r_t = ell, x_{1:t})
    R = np.zeros((T + 1, T + 1))
    R[0, 0] = 1.0

    # Sufficient statistics for each run length
    mu_params = [mu_prior]      # mean estimates
    kappa = [1.0 / sigma_prior**2]  # precision of mean

    changepoint_probs = []

    for t, x in enumerate(residuals):
        # Predictive probabilities for each run length
        pred_probs = []
        for ell in range(t + 1):
            # Predictive distribution: N(mu_ell, sigma_obs^2 + 1/kappa_ell)
            pred_var = sigma_obs**2 + 1.0 / kappa[ell]
            pred_prob = norm_pdf(x, mu_params[ell], np.sqrt(pred_var))
            pred_probs.append(pred_prob)

        pred_probs = np.array(pred_probs)

        # Growth probabilities
        R[t+1, 1:t+2] = R[t, 0:t+1] * pred_probs * (1 - hazard_rate)

        # Change-point probability
        R[t+1, 0] = np.sum(R[t, 0:t+1] * pred_probs * hazard_rate)

        # Normalize
        evidence = np.sum(R[t+1, :])
        R[t+1, :] /= evidence

        # Update sufficient statistics
        new_mu = []
        new_kappa = []
        # Run length 0: reset to prior
        new_mu.append(mu_prior)
        new_kappa.append(1.0 / sigma_prior**2)
        # Run lengths 1..t+1: update from previous
        for ell in range(t + 1):
            k_new = kappa[ell] + 1.0 / sigma_obs**2
            m_new = (kappa[ell] * mu_params[ell] + x / sigma_obs**2) / k_new
            new_kappa.append(k_new)
            new_mu.append(m_new)

        mu_params = new_mu
        kappa = new_kappa

        changepoint_probs.append(R[t+1, 0])

    return changepoint_probs, R
```

#### Advantages for Fire Detection

- Provides a full posterior over run length, not just a binary alarm
- Naturally handles uncertainty: the posterior on mu under each run length tells us
  the estimated fire signal strength
- Can detect the change point retroactively (the MAP run length tells us when it started)
- Handles multiple change points (fire start, fire growth, fire end)

#### Disadvantages

- O(T^2) memory and time in naive implementation (can be truncated to O(T*L_max))
- More complex to implement and tune than CUSUM
- Requires specifying priors (hazard rate, prior on mean)

### 3.5 Summary Comparison

| Method | Optimality | Complexity | Parameters | Best Use Case |
|--------|-----------|------------|------------|---------------|
| CUSUM  | Minimax optimal for change detection | O(1) per step | k_ref, h | Continuous monitoring, unknown change time |
| SPRT   | Optimal expected sample size for binary test | O(1) per step | alpha, beta, mu_1 | Testing a specific hypothesis |
| BOCPD  | Bayesian optimal given priors | O(T) per step | hazard_rate, priors | Rich posterior, multiple changes |

---

## 4. Practical Implementation for Geostationary Fire Detection

### 4.1 System Architecture

```
For each pixel under monitoring:

1. BACKGROUND MODEL (running continuously)
   - Maintain Kalman filter or DTC model for expected BT
   - Update with each cloud-free, fire-free observation
   - Output: predicted BT and prediction uncertainty at each time step

2. RESIDUAL COMPUTATION
   - r[k] = BT_observed[k] - BT_predicted[k]
   - Normalize: z[k] = r[k] / sigma_predicted[k]

3. SEQUENTIAL TEST (one or more of CUSUM/SPRT/BOCPD)
   - Update test statistic with each new residual
   - Check stopping criterion
   - Output: alarm / no-alarm / confidence level

4. ALARM PROCESSING
   - Spatial consistency check (adjacent pixels)
   - Cross-channel validation (3.9 um vs 11 um)
   - Integration with trigger-refine-confirm pipeline
```

### 4.2 Concrete Parameter Settings for Himawari AHI

#### Background Model

Using Kalman filter with harmonic DTC basis:

```
State vector:  x = [T_mean, a1, b1, a2, b2]  (mean + 2 harmonics)

State transition: F = I (parameters evolve slowly)

Process noise: Q = diag([0.01, 0.001, 0.001, 0.0005, 0.0005]^2) K^2
  (slow drift allowed: ~0.01 K/frame for mean, ~0.001 K/frame for harmonics)

Observation matrix: H = [1, cos(w*t), sin(w*t), cos(2w*t), sin(2w*t)]
  where w = 2*pi/24 and t is local solar time in hours

Observation noise: R = (0.3 K)^2  for nighttime Band 7
                   R = (0.5 K)^2  for daytime Band 7 (more atmospheric variability)
```

#### CUSUM Parameters

```
Target detection: mu_1 = 0.2 K  (minimum fire signal of interest)
Residual sigma:   sigma = 0.4 K (typical after DTC subtraction)
Normalized shift: delta = mu_1 / sigma = 0.5 sigma

Reference value:  k_ref = 0.25 sigma = 0.1 K  (half the target shift)
Decision threshold: h = 5 sigma = 2.0 K

Expected ARL_0: ~930 frames ≈ 155 hours ≈ 6.5 days (false alarm rate)
Expected ARL_1 at delta=0.5: ~38 frames ≈ 6.3 hours (detection delay)
Expected ARL_1 at delta=1.0: ~10 frames ≈ 1.7 hours
```

#### Multi-Scale CUSUM

Run multiple CUSUM detectors in parallel with different k_ref values to detect fires
of different sizes:

```
Detector 1: k_ref = 0.05 K, h = 2.0 K  → sensitive to very small fires (~50 m^2)
Detector 2: k_ref = 0.15 K, h = 2.0 K  → medium fires (~200 m^2)
Detector 3: k_ref = 0.50 K, h = 2.0 K  → larger fires (~1000 m^2)
```

An alarm from any detector triggers a fire candidate alert.

### 4.3 Handling Real-World Complications

#### Cloud Gaps

When a pixel is cloud-covered, no BT observation is available. Options:

1. **Skip and continue**: Do not update the CUSUM statistic. The fire signal is
   preserved in S[k] from before the cloud gap. Resume when cloud clears.

2. **Decay the CUSUM**: Apply a decay factor during gaps to prevent stale evidence
   from triggering late alarms:
   ```
   S[k] = max(0, gamma * S[k-1])    where gamma = exp(-dt / tau_decay)
   ```
   with tau_decay ~ 2-4 hours. This forgets accumulated evidence during long gaps.

3. **Increase uncertainty**: In the Kalman filter, do not update but let P_pred grow.
   When observation resumes, the Kalman gain will be large (trusting the new observation
   more), and the innovation will be evaluated against a wider predicted distribution.

#### Atmospheric State Corrections

Water vapor variations can cause 0.2-0.5 K fluctuations in 3.9 um BT that mimic or
mask fire signals. Mitigation approaches:

1. **Dual-channel normalization**: Use Band 14 (11.2 um) as a control channel.
   Water vapor affects both 3.9 um and 11 um, but fires affect 3.9 um much more.
   The BT difference (BT_3.9 - BT_11) removes much of the atmospheric signal.
   Apply CUSUM to the BT difference residual instead.

2. **NWP integration**: Use forecast water vapor profiles from ACCESS (Australian
   NWP model) or ERA5 reanalysis to compute expected atmospheric transmittance
   corrections. This can reduce atmospheric noise by ~50%.

3. **Spatial differencing**: Compare the target pixel's BT to the mean of surrounding
   fire-free pixels (spatial context). Atmospheric state is correlated on scales of
   10-50 km, so spatial differencing removes most atmospheric effects. This is what
   traditional contextual algorithms do, but here we apply it temporally.

#### Post-Fire Surface Changes

After a fire burns through a pixel, the surface emissivity and albedo change, which
shifts the baseline BT. This can cause false alarms on nearby pixels and missed
detections as the fire moves. Approaches:

1. **Adaptive baseline**: After a confirmed fire detection, flag the pixel and allow
   the Kalman filter to slowly adapt to the new surface properties over 1-4 weeks.

2. **Fire mask propagation**: Use confirmed fire detections to mask adjacent pixels
   as potentially fire-affected, adjusting their detection thresholds.

### 4.4 Integration with Existing Fire Products

The GOES-R ABI Fire Detection and Characterization (FDC) algorithm already uses
temporal filtering:

- Fire pixel classes 10-15: "instantaneous" (first/single) detections
- Fire pixel classes 30-35: "temporally filtered" detections, triggered when two or
  more co-located detections occur within a 12-hour interval

This simple persistence test reduces false alarm rates by up to 33%. Our sequential
detection approach generalizes this by:

1. Using optimal statistical tests (CUSUM) instead of ad-hoc persistence rules
2. Modeling the expected background (DTC) instead of using raw BT thresholds
3. Detecting sub-threshold fires that would never trigger a single-frame detection
4. Providing quantitative confidence levels rather than binary detect/no-detect

---

## 5. Expected Performance

### 5.1 Detection Delay vs Fire Size

Assuming:
- Background sigma = 0.4 K (after DTC subtraction)
- CUSUM with k_ref = 0.1 K, h = 2.0 K (h = 5 sigma)
- AHI Band 7 (3.9 um), 2 km pixels
- Fire temperature = 800 K, background = 300 K

BT increase from sub-pixel fire (from Planck function / mixed pixel model):

| Fire Area (m^2) | Pixel Fraction | BT Increase (K) | SNR/frame | CUSUM Delay (frames) | Delay (hours) |
|------------------|----------------|------------------|-----------|----------------------|---------------|
| 50               | 1.25e-5        | ~0.04            | 0.10      | >200                 | >33           |
| 100              | 2.5e-5         | ~0.08            | 0.20      | ~170                 | ~28           |
| 200              | 5.0e-5         | ~0.15            | 0.38      | ~65                  | ~11           |
| 500              | 1.25e-4        | ~0.35            | 0.88      | ~14                  | ~2.3          |
| 1,000            | 2.5e-4         | ~0.70            | 1.75      | ~5                   | ~0.8          |
| 2,000            | 5.0e-4         | ~1.40            | 3.50      | ~2                   | ~0.3          |
| 5,000            | 1.25e-3        | ~3.50            | 8.75      | 1 (instant)          | 0.17          |

Note: BT increase values are approximate and depend strongly on fire temperature,
background temperature, emissivity, and atmospheric transmittance. See sub_pixel_physics.md
for detailed calculations.

Key insight: Fires of 200-500 m^2 (0.02-0.05 ha) — invisible to any single-frame
geostationary algorithm — become detectable within 2-11 hours using sequential methods.
This fills the gap between the initial trigger (which requires ~1000+ m^2 for
single-frame detection) and LEO confirmation (which may take 6-12 hours).

### 5.2 False Alarm Rate Reduction

**Single-frame detection** (Shewhart-style threshold at 3 sigma):
- False alarm probability per frame per pixel: ~0.0013
- Over 144 frames/day across 1000 monitored pixels: ~187 false alarms/day

**CUSUM (h = 5 sigma, k = 0.5 sigma):**
- ARL_0 = 930 frames ≈ 155 hours
- False alarm rate per pixel: ~0.15/day
- Over 1000 monitored pixels: ~150 false alarms/day
- But these are at much higher sensitivity (detecting 0.5 sigma shifts vs 3 sigma)

**Key comparison**: For the same false alarm rate as a 3-sigma single-frame test
(ARL_0 ≈ 370 frames), CUSUM can detect 0.5-sigma shifts in ~27 frames vs not at all
for Shewhart. This is the fundamental advantage.

**Temporal persistence filter** (GOES-style, 2 detections in 12 hours):
- Reduces false alarm rate by factor of ~3-10x (operational experience)
- But requires the signal to exceed the single-frame threshold at least twice
- Cannot detect signals below the single-frame threshold

### 5.3 Receiver Operating Characteristic

At fixed ARL_0 = 1000 frames (~ 7 days false alarm interval), the detection probability
within a given time window as a function of fire signal strength:

| Signal (sigma units) | P(detect in 1 hr) | P(detect in 4 hr) | P(detect in 12 hr) |
|----------------------|--------------------|--------------------|--------------------|
| 0.25                 | < 0.01             | 0.05               | 0.15               |
| 0.50                 | 0.02               | 0.20               | 0.65               |
| 0.75                 | 0.10               | 0.55               | 0.92               |
| 1.00                 | 0.30               | 0.82               | 0.99               |
| 1.50                 | 0.70               | 0.98               | >0.99              |
| 2.00                 | 0.92               | >0.99              | >0.99              |

These values are derived from the CUSUM ARL tables and the relationship between detection
probability and detection delay distributions. Exact values depend on implementation
details (initial CUSUM value, handling of gaps, etc.).

---

## 6. Limitations and Open Questions

### 6.1 Model Error Dominance

The performance estimates above assume that residuals after DTC subtraction are
approximately Gaussian with constant variance. In practice:

- **Non-stationarity**: Residual variance changes with time of day (higher during
  daytime due to convective activity and atmospheric variability)
- **Non-Gaussianity**: Cloud contamination produces asymmetric outliers; partial cloud
  creates bimodal distributions
- **Autocorrelation**: Consecutive residuals are correlated (atmospheric state persists
  across 10-minute intervals). This reduces the effective number of independent samples
  and inflates the detection delay relative to the iid assumption.
- **Systematic bias**: DTC model errors can produce persistent positive or negative
  biases, particularly during weather transitions (frontal passages, post-rain cooling,
  heat waves). These can trigger false alarms.

The practical residual sigma is likely 0.5-1.0 K rather than the 0.3 K achievable
under ideal conditions, which roughly doubles the detection delays in the table above.

### 6.2 Atmospheric Variability at 3.9 um

The 3.9 um channel is particularly susceptible to atmospheric effects:

- **Water vapor**: Column water vapor variations of ~5 mm cause ~0.3-0.5 K BT changes.
  In convective environments (typical Australian fire season), water vapor can change
  rapidly on sub-hour timescales.
- **Aerosol**: Smoke from nearby fires affects atmospheric transmittance. This creates
  a paradoxical situation where fire detection performance degrades as more fires burn
  in the region.
- **Reflected solar**: During daytime, the 3.9 um signal includes reflected solar
  radiation. Sun glint, specular reflection from water bodies, and varying surface
  albedo all add noise.

Practical mitigation: Use the BT difference (3.9 um - 11 um) instead of raw 3.9 um BT
as the primary signal. This removes correlated atmospheric effects but reduces the
fire signal by ~20-30% (since 11 um also sees some fire signal).

### 6.3 Spatial Resolution Limits

At 2 km resolution, the sub-pixel fire signal decreases with pixel area. Himawari AHI
pixels at the latitude of NSW (~33 S) are actually larger than 2 km due to the viewing
geometry (Himawari is positioned at 140.7 E, ~0 N). The effective pixel size at NSW
latitudes is roughly 2.5 x 3.5 km, giving a pixel area of ~8.75 km^2 rather than 4 km^2.
This roughly halves the BT increase compared to nadir, shifting all detection delays
upward.

### 6.4 Computational Considerations

For a full-disk Himawari scene, there are ~22 million pixels, though only a fraction
are land pixels over the monitoring area. For NSW (~800,000 km^2), this is roughly
100,000 pixels at 2 km resolution.

Running a Kalman filter + CUSUM detector for each pixel requires:
- State storage: ~50 bytes/pixel (5 state variables + covariance + CUSUM state)
- Per-frame computation: ~100 floating-point operations per pixel
- Total per frame: ~10 million FLOPs → negligible (< 1 ms on modern hardware)
- Total storage: ~5 MB → negligible

This is computationally trivial. The bottleneck is data ingestion and cloud masking,
not the sequential detection itself.

### 6.5 Validation Challenges

- Ground truth for small fires (50-500 m^2) is extremely limited — these are below the
  detection threshold of most satellite instruments
- VIIRS (375 m pixels) can detect fires down to ~100-200 m^2 but only provides 2-4
  overpasses per day at NSW latitudes
- Validation against prescribed burns with known ignition times and areas would be ideal
- The method produces probabilistic detections, not binary yes/no, which complicates
  traditional commission/omission error analysis

### 6.6 Key Open Questions

1. **What is the achievable residual sigma?** The 0.3-0.8 K range spans a factor of
   ~2.5x in detection delay. Empirical characterization of AHI Band 7 residuals over
   NSW during fire season is critical.

2. **How autocorrelated are residuals?** If the autocorrelation timescale is ~30 minutes
   (3 frames), then the effective number of independent samples is reduced by 3x,
   increasing detection delays by ~sqrt(3) ≈ 1.7x.

3. **Can NWP-driven atmospheric corrections reduce residual sigma below 0.3 K?** If so,
   sequential detection of fires as small as 100 m^2 within 6-12 hours becomes feasible.

4. **What is the optimal channel combination?** BT_3.9 alone vs (BT_3.9 - BT_11) vs
   multi-channel fusion. The answer likely depends on time of day and atmospheric state.

5. **Should we use a nonparametric approach?** The Gaussian assumption may be poor.
   Rank-based or distribution-free CUSUM variants (e.g., Wilcoxon-based) may be more
   robust to outliers and non-Gaussianity.

---

## 7. References

### Sequential Detection Theory

- Page, E.S. (1954). "Continuous inspection schemes." Biometrika, 41(1/2), 100-115.
  [Original CUSUM paper]
- Wald, A. (1947). Sequential Analysis. John Wiley & Sons.
  [Original SPRT theory]
- Lorden, G. (1971). "Procedures for reacting to a change in distribution."
  Annals of Mathematical Statistics, 42(6), 1897-1908.
  [CUSUM minimax optimality]
- Moustakides, G.V. (1986). "Optimal stopping times for detecting changes in
  distributions." Annals of Statistics, 14(4), 1379-1387.
  [Exact CUSUM optimality proof]
- Adams, R.P. & MacKay, D.J.C. (2007). "Bayesian Online Changepoint Detection."
  arXiv:0710.3742.
  [BOCPD algorithm]

### DTC Modeling

- Gottsche, F.M. & Olesen, F.S. (2001). "Modelling of diurnal cycles of brightness
  temperature extracted from METEOSAT data." Remote Sensing of Environment, 76(3), 337-348.
  [Original GOT01 DTC model]
- Gottsche, F.M. & Olesen, F.S. (2009). "Modelling the effect of optical thickness on
  diurnal cycles of land surface temperature." Remote Sensing of Environment, 113(11),
  2306-2316.
  [GOT09 model with atmospheric optical thickness]
- Lu, L. et al. (2021). "A Four-Parameter Model for Estimating Diurnal Temperature
  Cycle From MODIS Land Surface Temperature Product." Journal of Geophysical Research:
  Atmospheres, 126(3), e2020JD033855.
- Hu, L. et al. (2020). "Improved estimates of monthly land surface temperature from
  MODIS using a diurnal temperature cycle (DTC) model." ISPRS Journal of
  Photogrammetry and Remote Sensing, 168, 131-140.

### Geostationary Fire Detection

- Roberts, G. & Wooster, M.J. (2014). "Development of a multi-temporal Kalman filter
  approach to geostationary active fire detection & fire radiative power (FRP)
  estimation." Remote Sensing of Environment, 152, 392-412.
  [Kalman filter DTC + fire detection for SEVIRI]
- Hally, B. et al. (2017). "A Broad-Area Method for the Diurnal Characterisation of
  Upwelling Medium Wave Infrared Radiation." Remote Sensing, 9(2), 167.
  [BAT method for MWIR DTC]
- Hally, B. et al. (2018). "Advances in active fire detection using a multi-temporal
  method for next-generation geostationary satellite data." International Journal of
  Digital Earth, 12(9), 1032-1044.
  [Multi-temporal FTA for geostationary fire detection]
- Filizzola, C. et al. (2017). "RST-FIRES, an exportable algorithm for early-fire
  detection and monitoring." Remote Sensing of Environment, 192, 167-191.
  [RST/ALICE approach for SEVIRI fire detection]
- de Lemos, A. et al. (2020). "Characterization of Background Temperature Dynamics of
  a Multitemporal Satellite Scene through Data Assimilation for Wildfire Detection."
  Remote Sensing, 12(10), 1661.
  [Data assimilation (EnKF, SIR, 4D-Var) for fire detection background]
- Xu, G. & Zhong, X. (2017). "Real-time wildfire detection and tracking in Australia
  using geostationary satellite." IEEE.
  [Himawari-8 spatiotemporal fire detection]
- Zhang, X. et al. (2023). "Near-real-time wildfire detection approach with Himawari-8/9
  geostationary satellite data integrating multi-scale spatial-temporal feature."
  International Journal of Applied Earth Observation and Geoinformation.

### GOES FDC Algorithm

- Schmidt, C. et al. (2013). "GOES-R ABI Fire Detection and Characterization Algorithm
  Theoretical Basis Document." NOAA/NESDIS/STAR.
  [GOES-R FDC ATBD with temporal filtering details]
- Xu, W. et al. (2021). "Improvements in high-temporal resolution active fire detection
  and FRP retrieval over the Americas using GOES-16 ABI with the geostationary Fire
  Thermal Anomaly (FTA) algorithm." Science of Remote Sensing, 3, 100016.

### Satellite Instrument Specifications

- AHI Band 7 (3.9 um): 2 km resolution, NEdT <= 0.16 K at 300 K
- AHI Band 14 (11.2 um): 2 km resolution, NEdT <= 0.10 K at 300 K
- Temporal resolution: 10-minute full disk, 2.5-minute Japan/target area
- Source: JMA Himawari-8/9 AHI specifications (eoportal.org)

### Fire Radiative Power

- Wooster, M.J. et al. (2003). "Retrieval of biomass combustion rates and totals from
  fire radiative power observations." Journal of Geophysical Research, 108(D24), 4744.
  [MIR radiance method for FRP]
- Dozier, J. (1981). "A method for satellite identification of surface temperature
  fields of subpixel resolution." Remote Sensing of Environment, 11, 221-229.
  [Original bi-spectral sub-pixel fire retrieval]

### Statistical Methods (NIST Handbook)

- NIST/SEMATECH e-Handbook of Statistical Methods, Section 6.3.2.3.
  https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc323.htm
  [CUSUM control charts: ARL tables, parameter selection]
