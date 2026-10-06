document.addEventListener("DOMContentLoaded", () => {
    const statusElement = document.getElementById("current-status");
    const statusCard = document.getElementById("status-card");
    const alertList = document.getElementById("alert-list");
    const confidenceElement = document.getElementById("confidence");
    const confidenceFill = document.getElementById("confidence-fill");

    const valSkeletons = document.getElementById("val-skeletons");
    const valVelocity = document.getElementById("val-velocity");
    const valAccel = document.getElementById("val-accel");

    const barSkeletons = document.getElementById("bar-skeletons");
    const barVelocity = document.getElementById("bar-velocity");
    const barAccel = document.getElementById("bar-accel");

    const headerClock = document.getElementById("header-clock");
    const feedTimestamp = document.getElementById("feed-timestamp");

    let previousStatus = "Analyzing...";

    // Reasonable ceilings for the telemetry bar meters (tune to real sensor range).
    const MAX_TARGETS = 10;
    const MAX_VELOCITY = 5;   // m/s
    const MAX_ACCEL = 2;      // g

    function setBar(el, value, max) {
        const pct = Math.max(0, Math.min(100, (value / max) * 100));
        el.style.width = `${pct}%`;
    }

    function firstNumber(str) {
        const match = String(str).match(/-?\d+(\.\d+)?/);
        return match ? parseFloat(match[0]) : 0;
    }

    function addLog(message, isDanger = false) {
        const li = document.createElement("li");
        const time = new Date().toLocaleTimeString('en-US', { hour12: false });

        if (isDanger) {
            li.className = "alert-danger";
        }

        li.innerHTML = `<span class="log-prefix">&gt;</span><span class="log-time">${time}</span> ${message}`;
        alertList.insertBefore(li, alertList.firstChild);

        if (alertList.children.length > 30) {
            alertList.removeChild(alertList.lastChild);
        }
    }

    function tickClock() {
        const now = new Date().toLocaleTimeString('en-US', { hour12: false });
        if (headerClock) headerClock.innerText = now;
        if (feedTimestamp) feedTimestamp.innerText = now;
    }

    async function fetchStatus() {
        try {
            const response = await fetch('/status');
            const data = await response.json();

            const currentStatus = data.status;
            const t = data.telemetry;

            if (t) {
                valSkeletons.innerText = t.skeletons;
                valVelocity.innerText = t.velocity;
                valAccel.innerText = t.accel;
                confidenceElement.innerText = `Confidence: ${t.confidence}`;

                setBar(barSkeletons, firstNumber(t.skeletons), MAX_TARGETS);
                setBar(barVelocity, firstNumber(t.velocity), MAX_VELOCITY);
                setBar(barAccel, firstNumber(t.accel), MAX_ACCEL);

                const confPct = firstNumber(t.confidence);
                if (confidenceFill) confidenceFill.style.width = `${Math.max(0, Math.min(100, confPct))}%`;
            }

            if (currentStatus === "Collapse" || currentStatus === "Altercation") {
                statusElement.innerText = currentStatus;
                statusCard.className = "card status-card status-danger";

                if (currentStatus !== previousStatus) {
                    addLog(`Critical: ${currentStatus} detected`, true);
                }
            } else if (currentStatus === "Normal") {
                statusElement.innerText = "Normal";
                statusCard.className = "card status-card status-normal";

                if (previousStatus === "Collapse" || previousStatus === "Altercation") {
                    addLog("Area returned to normal.");
                }
            } else if (currentStatus === "No Person") {
                statusElement.innerText = "No Target";
                statusCard.className = "card status-card";
            } else {
                statusElement.innerText = "Analyzing...";
                statusCard.className = "card status-card";
            }

            previousStatus = currentStatus;

        } catch (error) {
            console.error("Error fetching status:", error);
        }
    }

    tickClock();
    setInterval(tickClock, 1000);
    setInterval(fetchStatus, 300);
});