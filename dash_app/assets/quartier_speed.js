(function () {
    if (window.__cesipath_anim_bound) {
        return;
    }
    window.__cesipath_anim_bound = true;

    var contexts = [
        {
            key: "quartier",
            graphId: "graph-quartier-animation",
            playId: "quartier-play",
            pauseId: "quartier-pause",
            sliderId: "slider-quartier-vitesse"
        },
        {
            key: "generation",
            graphId: "graph-generation-animation",
            playId: "generation-play",
            pauseId: "generation-pause",
            sliderId: "slider-generation-vitesse"
        }
    ];

    var state = {};
    contexts.forEach(function (context) {
        state[context.key] = {speed: 1.0, playing: false};
    });

    function toNumber(value, fallback) {
        var parsed = Number(value);
        if (!isFinite(parsed) || parsed <= 0) {
            return fallback;
        }
        return parsed;
    }

    function getGraph(context) {
        var root = document.getElementById(context.graphId);
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

    function playOptions(context) {
        var duration = Math.max(1, Math.round(200 / state[context.key].speed));
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

    function play(context) {
        var gd = getGraph(context);
        if (!gd || typeof Plotly === "undefined" || !Plotly.animate) {
            return;
        }
        state[context.key].playing = true;
        Plotly.animate(gd, null, playOptions(context));
    }

    function pause(context) {
        var gd = getGraph(context);
        if (!gd || typeof Plotly === "undefined" || !Plotly.animate) {
            return;
        }
        state[context.key].playing = false;
        Plotly.animate(gd, [null], pauseOptions());
    }

    function applySpeedLive(context, speedValue) {
        state[context.key].speed = toNumber(speedValue, 1.0);
        if (!state[context.key].playing) {
            return;
        }
        var gd = getGraph(context);
        if (!gd || typeof Plotly === "undefined" || !Plotly.animate) {
            return;
        }
        Plotly.animate(gd, null, playOptions(context));
    }

    document.addEventListener("click", function (event) {
        contexts.forEach(function (context) {
            var playButton = event.target.closest("#" + context.playId);
            if (playButton) {
                event.preventDefault();
                play(context);
                return;
            }
            var pauseButton = event.target.closest("#" + context.pauseId);
            if (pauseButton) {
                event.preventDefault();
                pause(context);
            }
        });
    });

    document.addEventListener("input", function (event) {
        contexts.forEach(function (context) {
            var slider = event.target.closest("#" + context.sliderId);
            if (!slider) {
                return;
            }
            applySpeedLive(context, slider.value);
        });
    });

    document.addEventListener("change", function (event) {
        contexts.forEach(function (context) {
            var slider = event.target.closest("#" + context.sliderId);
            if (!slider) {
                return;
            }
            applySpeedLive(context, slider.value);
        });
    });
})();
