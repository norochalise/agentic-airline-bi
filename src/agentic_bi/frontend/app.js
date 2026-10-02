const form = document.getElementById("ask-form");
const questionInput = document.getElementById("question");
const submitButton = document.getElementById("submit-button");

const thread = document.getElementById("thread");
const messages = document.getElementById("messages");
const emptyState = document.getElementById("empty-state");

const themeToggle = document.getElementById("theme-toggle");
const newChatButton = document.getElementById("new-chat");


// -------------------------------------------------------------------
// Labels
// -------------------------------------------------------------------

// Early-exit routes finish before skill routing, so no skill is selected.
const ROUTE_LABELS = {
    current_airline_info: "official-web",
    interaction_response: "direct-reply",
};

const SOURCE_KINDS = {
    private_document: { label: "Doc", kind: "document" },
    dataset: { label: "Data", kind: "dataset" },
    live_official_web: { label: "Web", kind: "web" },
};

const DOCUMENT_NAMES = {
    "delta_2025_form_10k.pdf": "Delta 2025 Form 10-K",
    "delta_customer_service_plan_2026-09-25.txt": "Customer Service Plan",
    "delta_domestic_contract_plain_language_2026-08-18.pdf":
        "Domestic Contract of Carriage",
    "dot_september_2026_atcr_july_data.pdf": "DOT Air Travel Consumer Report",
};


// -------------------------------------------------------------------
// Small DOM helpers
// -------------------------------------------------------------------

function element(tag, className, text) {
    const node = document.createElement(tag);

    if (className) {
        node.className = className;
    }

    if (text !== undefined) {
        node.textContent = text;
    }

    return node;
}


function scrollToBottom() {
    thread.scrollTo({
        top: thread.scrollHeight,
        behavior: "smooth",
    });
}


function isHttpUrl(value) {
    try {
        const url = new URL(value);

        return url.protocol === "https:" || url.protocol === "http:";
    } catch {
        return false;
    }
}


function friendlyDocumentName(source) {
    return DOCUMENT_NAMES[source] ??
        source.replace(/\.[a-z0-9]+$/i, "").replace(/[_-]+/g, " ");
}


// -------------------------------------------------------------------
// Markdown
// -------------------------------------------------------------------

function renderMarkdown(markdownText) {
    const container = element("div", "answer");

    if (!markdownText) {
        container.textContent = "No answer was produced for this request.";
        return container;
    }

    if (
        typeof marked === "undefined" ||
        typeof DOMPurify === "undefined"
    ) {
        container.textContent = markdownText;
        return container;
    }

    const cleanedMarkdown = markdownText
        .replace(/&#x20;/gi, " ")
        .replace(/&nbsp;/gi, " ");

    container.innerHTML = DOMPurify.sanitize(
        marked.parse(cleanedMarkdown)
    );

    // Wide tables scroll inside their own frame.
    for (const table of container.querySelectorAll("table")) {
        const wrap = element("div", "table-wrap");
        table.replaceWith(wrap);
        wrap.appendChild(table);
    }

    // Links in answers open in a new tab.
    for (const link of container.querySelectorAll("a")) {
        link.target = "_blank";
        link.rel = "noopener noreferrer";
    }

    return container;
}


// -------------------------------------------------------------------
// Sources
// -------------------------------------------------------------------

function groupSources(items) {
    const groups = new Map();

    for (const item of items) {
        const isDocument = item.source_type === "private_document";

        const key = isDocument
            ? `doc:${item.title}`
            : `${item.source_type}:${item.url ?? item.title}`;

        if (!groups.has(key)) {
            groups.set(key, {
                ...item,
                title: isDocument
                    ? friendlyDocumentName(item.title)
                    : item.title,
                pages: [],
            });
        }

        if (item.page_number) {
            groups.get(key).pages.push(item.page_number);
        }
    }

    for (const group of groups.values()) {
        group.pages = [...new Set(group.pages)].sort((a, b) => a - b);
    }

    return [...groups.values()];
}


function renderSources(items) {
    if (!Array.isArray(items) || items.length === 0) {
        return null;
    }

    const list = element("div", "sources");

    for (const source of groupSources(items)) {
        const kind = SOURCE_KINDS[source.source_type] ?? {
            label: "Source",
            kind: "",
        };

        const hasLink = source.url && isHttpUrl(source.url);

        const chip = element(hasLink ? "a" : "span", "source-chip");

        if (hasLink) {
            chip.href = source.url;
            chip.target = "_blank";
            chip.rel = "noopener noreferrer";
            chip.title = source.url;
        }

        chip.appendChild(
            element("span", `source-badge ${kind.kind}`.trim(), kind.label)
        );
        chip.appendChild(
            element("span", "source-title", source.title || source.url)
        );

        if (source.pages.length > 0) {
            const label = source.pages.length === 1 ? "p." : "pp.";

            chip.appendChild(
                element(
                    "span",
                    "source-pages",
                    `${label} ${source.pages.join(", ")}`
                )
            );
        }

        list.appendChild(chip);
    }

    return list;
}


// -------------------------------------------------------------------
// Run details
// -------------------------------------------------------------------

function plural(count, singular, pluralForm = `${singular}s`) {
    return `${count} ${count === 1 ? singular : pluralForm}`;
}


function renderRunDetails(data, elapsedSeconds) {
    const details = element("details", "run-details");
    const summary = element("summary");

    const route =
        data.selected_skill ??
        ROUTE_LABELS[data.stop_reason] ??
        "—";

    summary.appendChild(element("span", "route-pill", route));

    const parts = [];

    if (data.knowledge_search_count) {
        parts.push(plural(data.knowledge_search_count, "doc search"));
    }

    if (data.data_analysis_count) {
        parts.push(
            plural(data.data_analysis_count, "data analysis", "data analyses")
        );
    }

    if (data.web_search_count) {
        parts.push(plural(data.web_search_count, "web search"));
    }

    parts.push(`${elapsedSeconds.toFixed(1)}s`);

    summary.appendChild(element("span", "", parts.join(" · ")));
    details.appendChild(summary);

    const grid = element("div", "run-grid");

    const metrics = [
        ["Skill", route],
        ["Stop reason", data.stop_reason ?? "—"],
        ["Steps", data.step_count ?? 0],
        ["Tool calls", data.tool_call_count ?? 0],
        ["Doc searches", data.knowledge_search_count ?? 0],
        ["Data analyses", data.data_analysis_count ?? 0],
        ["Web searches", data.web_search_count ?? 0],
        ["Errors", data.error_count ?? 0],
    ];

    for (const [label, value] of metrics) {
        const metric = element("div", "run-metric");
        metric.appendChild(element("span", "", label));
        metric.appendChild(element("strong", "", String(value)));
        grid.appendChild(metric);
    }

    details.appendChild(grid);

    if (data.run_id) {
        details.appendChild(element("div", "run-id", `Run ID ${data.run_id}`));
    }

    return details;
}


// -------------------------------------------------------------------
// Messages
// -------------------------------------------------------------------

function startConversation() {
    emptyState.classList.add("hidden");
    newChatButton.classList.remove("hidden");
}


function addUserMessage(text) {
    const message = element("div", "message message-user");
    message.appendChild(element("div", "bubble", text));
    messages.appendChild(message);
}


function addAssistantMessage() {
    const message = element("div", "message message-assistant");
    message.appendChild(element("div", "avatar", "AI"));

    const body = element("div", "assistant-body");

    const typing = element("div", "typing");
    const dots = element("span", "dots");
    dots.append(element("span"), element("span"), element("span"));
    typing.append(dots, element("span", "", "Analyzing…"));

    body.appendChild(typing);
    message.appendChild(body);
    messages.appendChild(message);

    return body;
}


function fillAssistantMessage(body, data, elapsedSeconds) {
    body.replaceChildren(renderMarkdown(data.answer));

    const sources = renderSources(data.sources);

    if (sources) {
        body.appendChild(sources);
    }

    body.appendChild(renderRunDetails(data, elapsedSeconds));
}


function showAssistantError(body, message) {
    body.replaceChildren(element("div", "message-error", message));
}


// -------------------------------------------------------------------
// Request
// -------------------------------------------------------------------

async function readErrorMessage(response) {
    let message = "The request could not be completed.";

    try {
        const errorData = await response.json();

        if (errorData.detail) {
            message =
                typeof errorData.detail === "string"
                    ? errorData.detail
                    : JSON.stringify(errorData.detail);
        }
    } catch {
        // Keep the default message.
    }

    return message;
}


function setBusy(isBusy) {
    submitButton.disabled = isBusy;
    questionInput.disabled = isBusy;
}


async function ask(question) {
    startConversation();
    addUserMessage(question);

    const body = addAssistantMessage();
    scrollToBottom();

    setBusy(true);

    const startedAt = performance.now();

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
            throw new Error(await readErrorMessage(response));
        }

        const data = await response.json();

        fillAssistantMessage(
            body,
            data,
            (performance.now() - startedAt) / 1000
        );

    } catch (error) {
        showAssistantError(
            body,
            error.message ||
            "Something went wrong while contacting the agent."
        );

    } finally {
        setBusy(false);
        questionInput.focus();
        scrollToBottom();
    }
}


// -------------------------------------------------------------------
// Composer
// -------------------------------------------------------------------

function resizeInput() {
    questionInput.style.height = "auto";
    questionInput.style.height = `${questionInput.scrollHeight}px`;
}


function submitQuestion() {
    const question = questionInput.value.trim();

    if (!question || submitButton.disabled) {
        return;
    }

    questionInput.value = "";
    resizeInput();

    ask(question);
}


form.addEventListener("submit", (event) => {
    event.preventDefault();
    submitQuestion();
});


questionInput.addEventListener("input", resizeInput);


// Enter sends; Shift+Enter inserts a new line.
questionInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        submitQuestion();
    }
});


for (const suggestion of document.querySelectorAll(".suggestion")) {
    suggestion.addEventListener("click", () => {
        const kind = suggestion.querySelector(".suggestion-kind");

        const question = suggestion.textContent
            .replace(kind ? kind.textContent : "", "")
            .trim();

        ask(question);
    });
}


newChatButton.addEventListener("click", () => {
    messages.replaceChildren();
    emptyState.classList.remove("hidden");
    newChatButton.classList.add("hidden");
    questionInput.focus();
});


// -------------------------------------------------------------------
// Theme
// -------------------------------------------------------------------

function currentTheme() {
    const explicit = document.documentElement.dataset.theme;

    if (explicit) {
        return explicit;
    }

    return window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
}


themeToggle.addEventListener("click", () => {
    const nextTheme = currentTheme() === "dark" ? "light" : "dark";

    document.documentElement.dataset.theme = nextTheme;

    try {
        localStorage.setItem("theme", nextTheme);
    } catch {
        // Storage unavailable; the choice lasts for this page only.
    }
});


// Firefox restores form-control state (including `disabled`) on reload,
// so a reload mid-request would otherwise leave the composer locked.
setBusy(false);
questionInput.focus();
