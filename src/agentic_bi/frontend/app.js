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
const errorCount = document.getElementById("error-count");
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


function displayResult(data) {
    answer.innerHTML = renderMarkdown(
        data.answer
    );

    selectedSkill.textContent =
        data.selected_skill ?? "—";

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

    errorCount.textContent =
        data.error_count ?? 0;

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