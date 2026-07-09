const payload = {
  project_name: "Diana Test Project",
  task_description: "Make hello world page prettier",
  files_touched: ["index.html"],
  mode: "advise",
};

fetch("http://127.0.0.1:8765/api/v1/route", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify(payload),
})
  .then((response) => response.json())
  .then((data) => {
    console.log(`Recommended model: ${data.recommended_model} (${data.selected_model_alias})`);
  });
