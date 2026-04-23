(function () {
    if (window.__cesipath_log_autoscroll_bound) {
        return;
    }
    window.__cesipath_log_autoscroll_bound = true;

    function scrollToBottom(node) {
        if (!node) {
            return;
        }
        node.scrollTop = node.scrollHeight;
    }

    function bindConsole(node) {
        if (!node || node.__cesipathLogObserver) {
            return;
        }

        var observer = new MutationObserver(function () {
            scrollToBottom(node);
        });
        observer.observe(node, {childList: true, subtree: true});
        node.__cesipathLogObserver = observer;

        if (typeof requestAnimationFrame === "function") {
            requestAnimationFrame(function () {
                scrollToBottom(node);
            });
        } else {
            scrollToBottom(node);
        }
    }

    function scanAndBind() {
        document.querySelectorAll(".log-console").forEach(bindConsole);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", scanAndBind);
    } else {
        scanAndBind();
    }

    var rootObserver = new MutationObserver(function () {
        scanAndBind();
    });
    rootObserver.observe(document.documentElement, {childList: true, subtree: true});
})();
