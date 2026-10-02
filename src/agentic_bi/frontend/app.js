const form = document.getElementById("ask-form");
const questionInput = document.getElementById("question");
const submitButton = document.getElementById("submit-button");

const loading = document.getElementById("loading");
const errorBox = document.getElementById("error");
const result = document.getElementById("result");

const answer = document.getElementById("answer");
const selectedSkill = document.getElementById("selected-skill");
const stopReason = document.getElementById("stop-reason");
const stepCount = document.getElementById("step-count");
const toolCallCount = document.getElementById("tool-call-count");
const knowledgeSearchCount = document.getElementById(
    "knowledge-search-count"
);
const dataAnalysisCount = document.getElementById(
    "data-analysis-count"
);
const webSearchCount = document.getElementById(
    "web-search-count"
);
const errorCount = document.getElementById("error-count");
const sources = document.getElementById("sources");
const sourceList = document.getElementById("source-list");
const runId = document.getElementById("run-id");


function setLoading(isLoading) {
    loading.classList.toggle("hidden", !isLoading);
    submitButton.disabled = isLoading;

    submitButton.textContent = isLoading
        ? "Analyzing..."
        : "Ask Agent";
}


function showError(message) {
    errorBox.textContent = message;
    errorBox.classList.remove("hidden");
}


function clearError() {
    errorBox.textContent = "";
    errorBox.classList.add("hidden");
}


function renderMarkdown(markdownText) {
    if (!markdownText) {
        return "";
    }

    if (
        typeof marked === "undefined" ||
        typeof DOMPurify === "undefined"
    ) {
        const fallback = document.createElement("div");
        fallback.textContent = markdownText;

        return fallback.innerHTML;
    }

    const cleanedMarkdown = markdownText
        .replace(/&#x20;/gi, " ")
        .replace(/&nbsp;/gi, " ");

    const html = marked.parse(cleanedMarkdown);

    return DOMPurify.sanitize(html);
}


const ROUTE_LABELS = {
    current_airline_info: "official-web",
    interaction_response: "direct-reply",
};


const SOURCE_LABELS = {
    private_document: ["Document", "document"],
    dataset: ["Dataset", "dataset"],
    live_official_web: ["Web", "web"],
};


function isHttpUrl(value) {
    try {
        const url = new URL(value);

        return url.protocol === "https:" || url.protocol === "http:";
    } catch {
        return false;
    }
}


function renderSources(items) {
    sourceList.replaceChildren();

    if (!Array.isArray(items) || items.length === 0) {
        sources.classList.add("hidden");
        return;
    }

    for (const item of items) {
        const row = document.createElement("li");
        row.className = "source-item";

        const [label, kind] = SOURCE_LABELS[item.source_type] ?? [
            "Source",
            "",
        ];

        const badge = document.createElement("span");
        badge.className = `source-type ${kind}`.trim();
        badge.textContent = label;
        row.appendChild(badge);

        if (item.url && isHttpUrl(item.url)) {
            const link = document.createElement("a");
            link.href = item.url;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = item.title || item.url;
            row.appendChild(link);
        } else {
            const title = document.createElement("span");
            title.textContent = item.title;
            row.appendChild(title);
        }

        if (item.page_number) {
            const page = document.createElement("span");
            page.className = "source-page";
            page.textContent = `p. ${item.page_number}`;
            row.appendChild(page);
        }

        sourceList.appendChild(row);
    }

    sources.classList.remove("hidden");
}


function displayResult(data) {
    answer.innerHTML = renderMarkdown(
        data.answer
    );

    // Early-exit routes finish before skill routing, so no skill is selected.
    selectedSkill.textContent =
        data.selected_skill ??
        ROUTE_LABELS[data.stop_reason] ??
        "—";

    stopReason.textContent =
        data.stop_reason ?? "—";

    stepCount.textContent =
        data.step_count ?? 0;

    toolCallCount.textContent =
        data.tool_call_count ?? 0;

    knowledgeSearchCount.textContent =
        data.knowledge_search_count ?? 0;

    dataAnalysisCount.textContent =
        data.data_analysis_count ?? 0;

    webSearchCount.textContent =
        data.web_search_count ?? 0;

    errorCount.textContent =
        data.error_count ?? 0;

    renderSources(data.sources);

    runId.textContent =
        data.run_id ?? "—";

    result.classList.remove("hidden");
}


form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const question = questionInput.value.trim();

    if (!question) {
        showError("Please enter a question.");
        return;
    }

    clearError();
    result.classList.add("hidden");
    setLoading(true);

    try {
        const response = await fetch("/ask", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                question: question,
            }),
        });

        if (!response.ok) {
            let message =
                "The request could not be completed.";

            try {
                const errorData =
                    await response.json();

                if (errorData.detail) {
                    message =
                        typeof errorData.detail === "string"
                            ? errorData.detail
                            : JSON.stringify(
                                errorData.detail
                            );
                }
            } catch {
                // Keep the default message.
            }

            throw new Error(message);
        }

        const data = await response.json();

        displayResult(data);

    } catch (error) {
        showError(
            error.message ||
            "Something went wrong while contacting the agent."
        );

    } finally {
        setLoading(false);
    }
});