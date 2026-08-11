// AeroRoute Application Logic

const API_BASE = "/api/v1";
let token = localStorage.getItem("token");
let email = localStorage.getItem("email");
let pollInterval = null;
let pollTimer = null;
let startTime = 0;

// DOM Elements
const authSection = document.getElementById("auth-section");
const plannerSection = document.getElementById("planner-section");
const loadingSection = document.getElementById("loading-section");
const dashboardSection = document.getElementById("dashboard-section");
const myTripsSection = document.getElementById("my-trips-section");
const myTripsBtn = document.getElementById("my-trips-btn");
const tripsList = document.getElementById("trips-list");
const noTrips = document.getElementById("no-trips");
const backToPlannerBtn = document.getElementById("back-to-planner-btn");

const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const plannerForm = document.getElementById("planner-form");

const tabLogin = document.getElementById("tab-login");
const tabRegister = document.getElementById("tab-register");

const userProfile = document.getElementById("user-profile");
const currentUsername = document.getElementById("current-username");
const logoutBtn = document.getElementById("logout-btn");
const backToFormBtn = document.getElementById("back-to-form-btn");

const authError = document.getElementById("auth-error");
const plannerError = document.getElementById("planner-error");

// Initialize application state
window.addEventListener("DOMContentLoaded", () => {
    updateAuthState();
    setupEventListeners();
});

// Setup DOM Event Listeners
function setupEventListeners() {
    // Auth Tab switching
    tabLogin.addEventListener("click", () => {
        tabLogin.classList.add("active");
        tabRegister.classList.remove("active");
        loginForm.classList.remove("hidden");
        registerForm.classList.add("hidden");
        authError.classList.add("hidden");
    });

    tabRegister.addEventListener("click", () => {
        tabRegister.classList.add("active");
        tabLogin.classList.remove("active");
        registerForm.classList.remove("hidden");
        loginForm.classList.add("hidden");
        authError.classList.add("hidden");
    });

    // Forms Submissions
    loginForm.addEventListener("submit", handleLogin);
    registerForm.addEventListener("submit", handleRegister);
    plannerForm.addEventListener("submit", handlePlanRequest);

    // Logout
    logoutBtn.addEventListener("click", logout);

    // My Trips
    if (myTripsBtn) {
        myTripsBtn.addEventListener("click", showMyTrips);
    }
    if (backToPlannerBtn) {
        backToPlannerBtn.addEventListener("click", () => {
            myTripsSection.classList.add("hidden");
            plannerSection.classList.remove("hidden");
        });
    }
    
    // Back to Planner Form
    backToFormBtn.addEventListener("click", () => {
        dashboardSection.classList.add("hidden");
        plannerSection.classList.remove("hidden");
    });

    // Dashboard Tabs Navigation
    document.querySelectorAll(".nav-tab").forEach(tab => {
        tab.addEventListener("click", (e) => {
            const targetTab = e.target.getAttribute("data-tab");
            
            // Toggle active classes on tabs
            document.querySelectorAll(".nav-tab").forEach(t => t.classList.remove("active"));
            e.target.classList.add("active");

            // Toggle sheets
            document.querySelectorAll(".tab-sheet").forEach(sheet => sheet.classList.remove("active"));
            document.getElementById(targetTab).classList.add("active");
        });
    });
}

// Authentication Handlers
function updateAuthState() {
    token = localStorage.getItem("token");
    email = localStorage.getItem("email");

    if (token) {
        authSection.classList.add("hidden");
        plannerSection.classList.remove("hidden");
        userProfile.classList.remove("hidden");
        currentUsername.textContent = email;
        myTripsSection.classList.add("hidden");
    } else {
        authSection.classList.remove("hidden");
        plannerSection.classList.add("hidden");
        userProfile.classList.add("hidden");
        dashboardSection.classList.add("hidden");
        loadingSection.classList.add("hidden");
        myTripsSection.classList.add("hidden");
    }
}

async function handleLogin(e) {
    e.preventDefault();
    authError.classList.add("hidden");

    const emailVal = document.getElementById("login-email").value;
    const passwordVal = document.getElementById("login-password").value;

    const params = new URLSearchParams();
    params.append("username", emailVal);
    params.append("password", passwordVal);

    try {
        const response = await fetch(`${API_BASE}/auth/token`, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body: params
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.message || "Invalid credentials.");
        }

        const data = await response.json();
        localStorage.setItem("token", data.access_token);
        localStorage.setItem("email", emailVal);
        updateAuthState();
        
        loginForm.reset();
    } catch (err) {
        authError.textContent = err.message;
        authError.classList.remove("hidden");
    }
}

async function handleRegister(e) {
    e.preventDefault();
    authError.classList.add("hidden");

    const emailVal = document.getElementById("register-email").value;
    const passwordVal = document.getElementById("register-password").value;

    try {
        const response = await fetch(`${API_BASE}/auth/register`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ email: emailVal, password: passwordVal })
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.message || "Registration failed.");
        }

        // Auto login on successful register
        const loginParams = new URLSearchParams();
        loginParams.append("username", emailVal);
        loginParams.append("password", passwordVal);
        
        const tokenResp = await fetch(`${API_BASE}/auth/token`, {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: loginParams
        });
        
        const tokenData = await tokenResp.json();
        localStorage.setItem("token", tokenData.access_token);
        localStorage.setItem("email", emailVal);
        updateAuthState();
        
        registerForm.reset();
    } catch (err) {
        authError.textContent = err.message;
        authError.classList.remove("hidden");
    }
}

function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("email");
    if (pollInterval) clearInterval(pollInterval);
    if (pollTimer) clearInterval(pollTimer);
    updateAuthState();
}

// Submitting Itinerary Planning Request
async function showMyTrips() {
    plannerSection.classList.add("hidden");
    dashboardSection.classList.add("hidden");
    loadingSection.classList.add("hidden");
    myTripsSection.classList.remove("hidden");
    
    tripsList.innerHTML = "";
    noTrips.classList.add("hidden");
    
    try {
        const response = await fetch(`${API_BASE}/trips`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        
        if (!response.ok) {
            throw new Error("Failed to fetch past trips.");
        }
        
        const trips = await response.json();
        if (trips.length === 0) {
            noTrips.classList.remove("hidden");
            return;
        }
        
        trips.forEach(t => {
            const card = document.createElement("div");
            card.className = "card";
            card.style.background = "rgba(15, 23, 42, 0.4)";
            card.style.border = "1px solid rgba(45, 212, 191, 0.2)";
            card.style.padding = "12px";
            card.style.borderRadius = "8px";
            card.style.cursor = "pointer";
            card.style.transition = "transform 0.2s, border-color 0.2s";
            
            card.addEventListener("mouseenter", () => {
                card.style.borderColor = "rgba(45, 212, 191, 0.6)";
                card.style.transform = "translateY(-2px)";
            });
            card.addEventListener("mouseleave", () => {
                card.style.borderColor = "rgba(45, 212, 191, 0.2)";
                card.style.transform = "none";
            });
            
            const statusClass = t.status === "completed" ? "text-success" : (t.status === "failed" ? "text-danger" : "text-warning");
            const statusLabel = t.status.toUpperCase();
            
            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <strong style="color: #2dd4bf; font-size: 14px;">${t.destination}</strong>
                    <span style="font-size: 11px; padding: 2px 6px; border-radius: 4px; background: rgba(0,0,0,0.3);" class="${statusClass}">${statusLabel}</span>
                </div>
                <div style="font-size: 12px; color: #94a3b8; display: flex; gap: 15px;">
                    <span>Date: ${t.start_date}</span>
                    <span>Days: ${t.duration_days}</span>
                    <span>Budget: $${t.budget_usd}</span>
                </div>
                <div style="margin-top: 8px; display: flex; gap: 10px; font-size: 16px;">
                    <span title="Email">✉️</span>
                    <span title="Download">⬇️</span>
                </div>
            `;
            
            card.addEventListener("click", () => {
                if (t.status === "completed") {
                    myTripsSection.classList.add("hidden");
                    loadingSection.classList.remove("hidden");
                    resetStatusTracker();
                    document.getElementById("timer-val").textContent = "-";
                    loadCompletedPlan(t.trip_id);
                } else if (t.status === "planning") {
                    myTripsSection.classList.add("hidden");
                    loadingSection.classList.remove("hidden");
                    startPolling(t.trip_id);
                } else {
                    alert(`This trip plan has status '${t.status}'. You can select it and try to re-plan inside the details, or plan a new one.`);
                }
            });
            
            tripsList.appendChild(card);
        });
    } catch (err) {
        tripsList.innerHTML = `<div class="error-alert">${err.message}</div>`;
    }
}

// Submitting Itinerary Planning Request
async function handlePlanRequest(e) {
    e.preventDefault();
    plannerError.classList.add("hidden");

    const origin = document.getElementById("origin").value;
    const destination = document.getElementById("destination").value;
    const departureDate = document.getElementById("departure_date").value;
    const returnDate = document.getElementById("return_date").value;
    const budget = parseFloat(document.getElementById("budget").value);
    const travelStyle = document.getElementById("travel_style").value;
    const partySize = parseInt(document.getElementById("party_size").value);

    // Get selected interests
    const interests = Array.from(document.querySelectorAll("input[name='interests']:checked"))
        .map(cb => cb.value);

    // Get selected cuisines
    const cuisines = Array.from(document.querySelectorAll("input[name='cuisines']:checked"))
        .map(cb => cb.value);

    if (interests.length === 0) {
        plannerError.textContent = "Please select at least one interest.";
        plannerError.classList.remove("hidden");
        return;
    }
    
    if (cuisines.length === 0) {
        plannerError.textContent = "Please select at least one cuisine preference.";
        plannerError.classList.remove("hidden");
        return;
    }

    const payload = {
        destination,
        origin,
        departure_date: departureDate,
        return_date: returnDate,
        budget_usd: budget,
        travel_style: travelStyle,
        party_size: partySize,
        interests,
        cuisines
    };

    try {
        const response = await fetch(`${API_BASE}/plan`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.message || "Planning request failed.");
        }

        const data = await response.json();
        const tripId = data.trip_id;

        // Switch to Loading View
        plannerSection.classList.add("hidden");
        loadingSection.classList.remove("hidden");

        // Start status polling
        startPolling(tripId);
    } catch (err) {
        plannerError.textContent = err.message;
        plannerError.classList.remove("hidden");
    }
}

// Background Task Status Polling
function startPolling(tripId) {
    startTime = Date.now();
    let currentProgress = 5;
    
    // Reset steps UI
    resetStatusTracker();
    document.getElementById("timer-val").textContent = "0";

    // Polling timer display
    pollTimer = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        document.getElementById("timer-val").textContent = elapsed;
    }, 1000);

    pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/status/${tripId}`, {
                headers: { "Authorization": `Bearer ${token}` }
            });

            if (!response.ok) {
                throw new Error("Failed to check status.");
            }

            const data = await response.json();
            const status = data.status;

            // Increment progress bar slowly
            if (currentProgress < 95) {
                currentProgress += 5;
                document.getElementById("progress-bar-fill").style.width = `${currentProgress}%`;
            }

            // Update steps layout
            updateStatusTracker(status);

            if (status === "completed") {
                clearInterval(pollInterval);
                clearInterval(pollTimer);
                document.getElementById("progress-bar-fill").style.width = "100%";
                
                // Fetch completed plan details
                await loadCompletedPlan(tripId);
            } else if (status === "failed") {
                clearInterval(pollInterval);
                clearInterval(pollTimer);
                
                // Set step failed
                const activeStep = document.querySelector(".status-step.active");
                if (activeStep) {
                    activeStep.classList.remove("active");
                    activeStep.classList.add("failed");
                }
                
                alert("Planning task failed in background. Please review your settings or retry.");
                
                // Back to form
                loadingSection.classList.add("hidden");
                plannerSection.classList.remove("hidden");
            }
        } catch (err) {
            console.error(err);
        }
    }, 3000);
}

function resetStatusTracker() {
    document.querySelectorAll(".status-step").forEach(step => {
        step.className = "status-step";
    });
    document.getElementById("step-task").classList.add("active");
    document.getElementById("progress-bar-fill").style.width = "5%";
}

function updateStatusTracker(status) {
    const taskStep = document.getElementById("step-task");
    const agentsStep = document.getElementById("step-agents");
    const curatingStep = document.getElementById("step-curating");
    const budgetStep = document.getElementById("step-budget");

    if (status === "planning") {
        taskStep.className = "status-step completed";
        
        const elapsed = (Date.now() - startTime) / 1000;
        if (elapsed > 40) {
            agentsStep.className = "status-step completed";
            curatingStep.className = "status-step active";
        } else if (elapsed > 10) {
            taskStep.className = "status-step completed";
            agentsStep.className = "status-step active";
        }
    }
}

// Fetch Completed Plan & Render Dashboard
async function loadCompletedPlan(tripId) {
    try {
        const response = await fetch(`${API_BASE}/trips/${tripId}`, {
            headers: { "Authorization": `Bearer ${token}` }
        });

        if (!response.ok) {
            throw new Error("Could not load trip details.");
        }

        const plan = await response.json();
        
        // Hide loader, show dashboard
        loadingSection.classList.add("hidden");
        dashboardSection.classList.remove("hidden");

        // Compile Dashboard Data
        renderItineraryDashboard(plan);
    } catch (err) {
        alert("Error loading completed plan: " + err.message);
    }
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
        .format(amount || 0);
}

function renderItineraryDashboard(plan) {
    // 1. Header Details
    document.getElementById("dashboard-dest").textContent = plan.destination;
    document.getElementById("dashboard-origin").textContent = plan.origin;
    document.getElementById("dashboard-dates").textContent = `${plan.departure_date} to ${plan.return_date}`;
    document.getElementById("dashboard-party").textContent = `${plan.packing_list ? 'Planned' : 'Itinerary'}`;

    // 2. Budget Card & Summary costs
    const summary = plan.cost_summary || {};
    const remaining = summary.budget_remaining_usd || 0.00;
    const total = summary.total_usd || 0.00;
    
    document.getElementById("dashboard-budget-rem").textContent = formatCurrency(remaining);
    
    // Remaining status card color
    const budgetStatusCard = document.getElementById("budget-status-card");
    if (remaining < 0) {
        budgetStatusCard.style.borderColor = "var(--error)";
        document.getElementById("dashboard-budget-pct").textContent = "Over budget!";
        document.getElementById("dashboard-budget-pct").style.color = "var(--error)";
    } else {
        budgetStatusCard.style.borderColor = "var(--glass-border)";
        document.getElementById("dashboard-budget-pct").textContent = "Within limits";
        document.getElementById("dashboard-budget-pct").style.color = "var(--success)";
    }

    // Cost values list
    document.getElementById("summary-cost-flights").textContent = formatCurrency(summary.flights_usd);
    document.getElementById("summary-cost-hotels").textContent = formatCurrency(summary.hotels_usd);
    document.getElementById("summary-cost-activities").textContent = formatCurrency(summary.activities_usd);
    document.getElementById("summary-cost-food").textContent = formatCurrency(summary.food_usd);
    document.getElementById("summary-cost-total").textContent = formatCurrency(total);

    // 3. Safety Summary
    const safety = plan.safety_advisory || {};
    const level = (safety.advisory_level || "low").toLowerCase();
    const lvlBadge = document.getElementById("summary-safety-level");
    lvlBadge.className = `advisory-badge ${level}`;
    lvlBadge.textContent = `${level} Risk`;
    document.getElementById("summary-safety-desc").textContent = safety.advisory_summary || "Safety advisory details loaded successfully.";

    // Safety Tab details
    document.getElementById("safety-source").textContent = safety.advisory_source || "State Department";
    const emergency = safety.local_emergency_numbers || {};
    document.getElementById("safety-police").textContent = emergency.police || "911";
    document.getElementById("safety-ambulance").textContent = emergency.ambulance || "911";
    document.getElementById("safety-full-desc").textContent = safety.advisory_summary || "Normal security conditions are present in the target destination.";

    // 4. Highlight Cards
    const highlightsContainer = document.getElementById("overview-highlights");
    highlightsContainer.innerHTML = "";
    
    // Add primary hotel
    const hotels = plan.hotel_options || [];
    if (hotels.length > 0) {
        highlightsContainer.innerHTML += `
            <div class="highlight-card card glass inner-card">
                <h4>🏨 Staying At</h4>
                <p><strong>${hotels[0].name}</strong></p>
                <p class="subtitle" style="margin-bottom:0;">${hotels[0].why_recommended || 'Highly rated option.'}</p>
            </div>
        `;
    }

    // Add primary flight
    const flightsObj = plan.flight_options || {};
    const flights = flightsObj.flights || [];
    if (flights.length > 0) {
        highlightsContainer.innerHTML += `
            <div class="highlight-card card glass inner-card">
                <h4>✈️ Flight Tickets</h4>
                <p><strong>${flights[0].airline}</strong></p>
                <p class="subtitle" style="margin-bottom:0;">${flights[0].why_recommended || 'Best value option.'}</p>
            </div>
        `;
    }

    // 5. Flights List
    const flightsContainer = document.getElementById("flights-container");
    flightsContainer.innerHTML = "";
    if (flights.length === 0) {
        flightsContainer.innerHTML = "<p class='subtitle'>No flights curated.</p>";
    } else {
        flights.forEach(f => {
            flightsContainer.innerHTML += `
                <div class="deal-card">
                    <div class="deal-main">
                        <strong>${f.airline}</strong> <span class="badge" style="color:var(--primary); font-size:0.8rem; margin-left:0.5rem;">[${f.type || 'Option'}]</span>
                        <p class="subtitle" style="margin-bottom:0; font-size:0.85rem;">Duration: ${f.duration || 'N/A'} • Stops: ${f.stops}</p>
                        <p class="deal-why">${f.why_recommended || ''}</p>
                    </div>
                    <div class="deal-cost">${formatCurrency(f.price_usd)}</div>
                </div>
            `;
        });
    }

    // 6. Hotels List
    const hotelsContainer = document.getElementById("hotels-container");
    hotelsContainer.innerHTML = "";
    if (hotels.length === 0) {
        hotelsContainer.innerHTML = "<p class='subtitle'>No lodging options curated.</p>";
    } else {
        hotels.forEach(h => {
            hotelsContainer.innerHTML += `
                <div class="deal-card">
                    <div class="deal-main">
                        <strong>${h.name}</strong>
                        <p class="subtitle" style="margin-bottom:0; font-size:0.85rem;">Address: ${h.address || 'Local'}</p>
                        <p class="deal-why">${h.why_recommended || ''}</p>
                    </div>
                    <div class="deal-cost">${formatCurrency(h.price_per_night_usd)}<span style="font-size:0.75rem; font-weight:400; color:var(--text-muted);">/nt</span></div>
                </div>
            `;
        });
    }

    // 7. Weather Table
    const weatherTbody = document.getElementById("weather-tbody");
    weatherTbody.innerHTML = "";
    const weatherList = plan.weather_forecast || [];
    if (weatherList.length === 0) {
        weatherTbody.innerHTML = "<tr><td colspan='3' class='subtitle'>No forecast available.</td></tr>";
    } else {
        weatherList.forEach(w => {
            weatherTbody.innerHTML += `
                <tr>
                    <td><strong>${w.date}</strong></td>
                    <td>${w.description}</td>
                    <td><span class="feasible-badge ${w.outdoor_feasible ? 'yes' : 'no'}">${w.outdoor_feasible ? '🌳 Outdoor Friendly' : '🏠 Indoor Advised'}</span></td>
                </tr>
            `;
        });
    }

    // 8. Packing Checklist
    const packing = plan.packing_list || {};
    renderChecklist("packing-base", packing.base_items || ["Passport", "Toiletries", "Charger"]);
    renderChecklist("packing-weather", packing.weather_driven_items || ["Umbrella / rain coat"]);
    renderChecklist("packing-activity", packing.activity_driven_items || ["Hiking boots", "Water bottle"]);

    // 9. Schedule/Timeline Timeline
    const scheduleTimeline = document.getElementById("schedule-timeline");
    scheduleTimeline.innerHTML = "";

    const activities = plan.curated_activities || [];
    const restaurants = plan.curated_restaurants || [];

    if (activities.length === 0 && restaurants.length === 0) {
        scheduleTimeline.innerHTML = "<p class='subtitle'>No schedule itinerary compiled.</p>";
    } else {
        // Render Curated Sights Day Timeline
        let dayHtml = `
            <div class="timeline-day">
                <div class="day-title">🎟️ Recommended Sightseeing & Local Sights</div>
                <div class="day-events">
        `;
        
        if (activities.length === 0) {
            dayHtml += `<p class="subtitle">No outdoor activities curated.</p>`;
        } else {
            activities.forEach((act, idx) => {
                dayHtml += `
                    <div class="event-card">
                        <div class="event-header">
                            <span class="event-time">Sight #${idx + 1} • ${act.category || 'Sight'}</span>
                            <span class="event-cost">${act.cost_usd > 0 ? formatCurrency(act.cost_usd) : 'Free Admission'}</span>
                        </div>
                        <strong>${act.name}</strong>
                        <p class="subtitle" style="margin-bottom:0;">${act.description || ''}</p>
                        <p class="event-why">📌 Interest Match: <strong>${act.matching_interest || 'General'}</strong> • ${act.why_recommended || ''}</p>
                    </div>
                `;
            });
        }
        
        dayHtml += `
                </div>
            </div>
            
            <div class="timeline-day">
                <div class="day-title">🍴 Curated Local Dining & Cafe Stops</div>
                <div class="day-events">
        `;

        if (restaurants.length === 0) {
            dayHtml += `<p class="subtitle">No local dining compiled.</p>`;
        } else {
            restaurants.forEach((r, idx) => {
                dayHtml += `
                    <div class="event-card">
                        <div class="event-header">
                            <span class="event-time">Dining #${idx + 1} • Cuisine: ${r.cuisine || 'Local'}</span>
                            <span class="event-cost">${formatCurrency(r.cost_per_person_usd)}/person</span>
                        </div>
                        <strong>${r.name}</strong>
                        <p class="subtitle" style="margin-bottom:0;">Address: ${r.address || 'Nearby'}</p>
                        <p class="event-why">🍷 Recommendation: ${r.why_recommended || ''}</p>
                    </div>
                `;
            });
        }

        dayHtml += `
                </div>
            </div>
        `;
        
        scheduleTimeline.innerHTML = dayHtml;
    }
}

function renderChecklist(containerId, items) {
    const container = document.getElementById(containerId);
    container.innerHTML = "";
    if (items.length === 0) {
        container.innerHTML = "<p class='subtitle'>None required.</p>";
    } else {
        items.forEach((item, idx) => {
            container.innerHTML += `
                <label class="checklist-item">
                    <input type="checkbox" id="${containerId}-chk-${idx}">
                    <span>${item}</span>
                </label>
            `;
        });
    }
}
