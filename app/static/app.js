// Немного поведения поверх серверных страниц: без фреймворка, всё работает и без JS.

document.addEventListener("DOMContentLoaded", () => {
  initWordRows();
  initReview();
  initConfirms();
  initLoadingButtons();
});

function initWordRows() {
  const rows = document.querySelector("[data-rows]");
  if (!rows) return;
  const template = document.querySelector("[data-row-template]");
  const countButton = document.querySelector("[data-count-button]");
  let nextIndex = rows.querySelectorAll("[data-row]").length;

  const plural = (n, one, few, many) => {
    if (n % 10 === 1 && n % 100 !== 11) return one;
    if (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14)) return few;
    return many;
  };

  const updateCount = () => {
    const n = rows.querySelectorAll("[data-include]:checked").length;
    countButton.textContent = n ? `Добавить ${n} ${plural(n, "карточку", "карточки", "карточек")}` : "Добавить карточки";
    countButton.disabled = n === 0;
  };

  rows.addEventListener("change", (e) => { if (e.target.matches("[data-include]")) updateCount(); });
  rows.addEventListener("click", (e) => {
    const edit = e.target.closest("[data-edit]");
    if (edit) edit.closest("[data-row]").classList.add("is-editing");
  });

  document.querySelector("[data-add-row]")?.addEventListener("click", () => {
    const html = template.innerHTML.replaceAll("__i__", String(nextIndex++));
    rows.insertAdjacentHTML("beforeend", html);
    const row = rows.lastElementChild;
    row.querySelector("input[name$='-text']").focus();
    updateCount();
  });

  updateCount();
}

function initReview() {
  const review = document.querySelector("[data-review]");
  if (!review) return;
  const flip = () => review.classList.add("is-flipped");
  review.querySelector("[data-flip]")?.addEventListener("click", flip);

  review.querySelectorAll("[data-speak]").forEach((btn) => {
    if (!("speechSynthesis" in window)) { btn.hidden = true; return; }
    btn.addEventListener("click", () => {
      const u = new SpeechSynthesisUtterance(btn.dataset.speak);
      u.lang = "en-US";
      u.rate = 0.9;
      speechSynthesis.cancel();
      speechSynthesis.speak(u);
    });
  });

  document.addEventListener("keydown", (e) => {
    if (e.target.matches("input, textarea, select")) return;
    if (e.code === "Space" && !review.classList.contains("is-flipped")) {
      e.preventDefault();
      flip();
    } else if (review.classList.contains("is-flipped") && ["1", "2", "3", "4"].includes(e.key)) {
      review.querySelector(`[data-grade="${e.key}"]`)?.click();
    }
  });
}

function initConfirms() {
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    });
  });
}

function initLoadingButtons() {
  document.querySelectorAll("button[data-loading]").forEach((btn) => {
    btn.form?.addEventListener("submit", () => {
      setTimeout(() => { btn.disabled = true; btn.textContent = btn.dataset.loading; }, 0);
    });
  });
}
