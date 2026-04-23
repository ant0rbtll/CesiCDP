(function () {
    if (window.__quartier_anim_bound) {
        return;
    }
    window.__quartier_anim_bound = true;

    var state = {
        speed: 1.0,
        playing: false
    };

    function toNumber(value, fallback) {
        var parsed = Number(value);
        if (!isFinite(parsed) || parsed <= 0) {
            return fallback;
        }
        return parsed;
    }

    function getGraph() {
        var root = document.getElementById("graph-quartier-animation");
        if (!root) {
            return null;
        }
        if (root.data && root.layout) {
            return root;
        }
        var nested = root.querySelector(".js-plotly-plot");
        if (nested && nested.data && nested.layout) {
            return nested;
        }
        return null;
    }

    function playOptions() {
        var duration = Math.max(1, Math.round(200 / state.speed));
        return {
            frame: {duration: duration, redraw: true},
            transition: {duration: 0},
            fromcurrent: true,
            mode: "immediate"
        };
    }

    function pauseOptions() {
        return {
            frame: {duration: 0},
            transition: {duration: 0},
            mode: "immediate"
        };
    }

    function play() {
        var gd = getGraph();
        if (!gd || typeof Plotly === "undefined" || !Plotly.animate) {
            return;
        }
        state.playing = true;
        Plotly.animate(gd, null, playOptions());
    }

    function pause() {
        var gd = getGraph();
        if (!gd || typeof Plotly === "undefined" || !Plotly.animate) {
            return;
        }
        state.playing = false;
        Plotly.animate(gd, [null], pauseOptions());
    }

    function applySpeedLive(speedValue) {
        state.speed = toNumber(speedValue, 1.0);
        if (!state.playing) {
            return;
        }
        var gd = getGraph();
        if (!gd || typeof Plotly === "undefined" || !Plotly.animate) {
            return;
        }
        Plotly.animate(gd, null, playOptions());
    }

    document.addEventListener("click", function (event) {
        var playButton = event.target.closest("#quartier-play");
        if (playButton) {
            event.preventDefault();
            play();
            return;
        }
        var pauseButton = event.target.closest("#quartier-pause");
        if (pauseButton) {
            event.preventDefault();
            pause();
        }
    });

    document.addEventListener("input", function (event) {
        var slider = event.target.closest("#slider-quartier-vitesse");
        if (!slider) {
            return;
        }
        applySpeedLive(slider.value);
    });

    document.addEventListener("change", function (event) {
        var slider = event.target.closest("#slider-quartier-vitesse");
        if (!slider) {
            return;
        }
        applySpeedLive(slider.value);
    });
})();
