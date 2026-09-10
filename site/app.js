// Nut sao chep: doc noi dung tu <template id="prompt-<key>">, khong hardcode tung skill.
// Them skill moi = them mot <template> + mot nut, khong phai sua file nay.
const status = document.querySelector("#copy-status");

document.querySelectorAll("[data-copy-prompt]").forEach((button) => {
  button.addEventListener("click", async () => {
    const template = document.querySelector(`#prompt-${button.dataset.copyPrompt}`);
    if (!template) {
      status.textContent = "Khong tim thay noi dung de sao chep.";
      return;
    }
    try {
      await navigator.clipboard.writeText(template.content.textContent.trim());
      status.textContent = "Đã sao chép. Hãy dán vào AI của bạn.";
    } catch {
      status.textContent = "Không thể tự sao chép; hãy bôi đen nội dung bên trên.";
    }
  });
});
