document.addEventListener("DOMContentLoaded", function () {
  const encodeSection = document.getElementById("encodeSection");
  const decodeSection = document.getElementById("decodeSection");
  const encodeTab = document.getElementById("encodeTab");
  const decodeTab = document.getElementById("decodeTab");

  const downloadLink = document.getElementById("downloadLink");
  const downloadDecodedImage = document.getElementById("downloadDecodedImage");
  const responseText = document.getElementById("response");

  const encodingTypeSelect = document.getElementById("encodingType");
  const hiddenFileTypeSelect = document.getElementById("hiddenFileType");

  const coverFileInput = document.getElementById("coverFileUpload");
  const hiddenFileInput = document.getElementById("hiddenFileUpload");
  const hiddenVideoInput = document.getElementById("hiddenVideoUpload");
  const hiddenDataTextarea = document.getElementById("hiddenData");
  const dataType = document.getElementById("dataType");
  const dataTypeDesc = document.getElementById("dataTypeDesc");

  const decodeTypeSelect = document.getElementById("decodeType");
  const decodeFileInput = document.getElementById("fileUploadDecode");

  const hiddenFileTypeLabel = document.getElementById("hiddenFileTypeLabel");
  const hiddenFileTypeDesc = document.getElementById("hiddenFileTypeDesc");
  const decodeFileTypeDesc = document.getElementById("decodeTypeDesc");
  const hiddenDataLabel = document.getElementById("hiddenDataLabel");
  const hiddenFileUploadLabel = document.getElementById(
    "hiddenFileUploadLabel"
  );
  const hiddenVideoUploadLabel = document.getElementById(
    "hiddenVideoUploadLabel"
  );

  const encodeForm = document.getElementById("encodeForm");
  const decodeForm = document.getElementById("decodeForm");

  function showFullscreenLoader() {
    document.getElementById("fullscreenLoader").style.display = "flex";
    document.body.style.overflow = "hidden";
  }

  function hideFullscreenLoader() {
    document.getElementById("fullscreenLoader").style.display = "none";
    document.body.style.overflow = "auto";
  }

  function switchTab(tab) {
    if (tab === "encode") {
      encodeSection.classList.add("active");
      encodeSection.removeAttribute("aria-hidden");
      decodeSection.classList.remove("active");
      decodeSection.setAttribute("aria-hidden", "true");
      encodeTab.classList.add("active");
      encodeTab.setAttribute("aria-selected", "true");
      encodeTab.tabIndex = 0;
      decodeTab.classList.remove("active");
      decodeTab.setAttribute("aria-selected", "false");
      decodeTab.tabIndex = -1;
    } else {
      decodeSection.classList.add("active");
      decodeSection.removeAttribute("aria-hidden");
      encodeSection.classList.remove("active");
      encodeSection.setAttribute("aria-hidden", "true");
      decodeTab.classList.add("active");
      decodeTab.setAttribute("aria-selected", "true");
      decodeTab.tabIndex = 0;
      encodeTab.classList.remove("active");
      encodeTab.setAttribute("aria-selected", "false");
      encodeTab.tabIndex = -1;
      dataType.style.display = "none";
      dataTypeDesc.style.display = "none";
    }
  }

  function updateEncodingInputs() {
    const encodingType = encodingTypeSelect.value;
    const hiddenFileType = hiddenFileTypeSelect.value;

    hiddenDataLabel.style.display = "none";
    hiddenDataTextarea.style.display = "none";
    hiddenFileUploadLabel.style.display = "none";
    hiddenFileInput.style.display = "none";
    hiddenVideoUploadLabel.style.display = "none";
    hiddenVideoInput.style.display = "none";
    hiddenFileTypeLabel.style.display = "none";
    hiddenFileTypeSelect.style.display = "none";
    hiddenFileTypeDesc.style.display = "none";
    hiddenFileInput.value = "";
    hiddenVideoInput.value = "";
    hiddenDataTextarea.value = "";

    if (encodingType === "text") {
      coverFileInput.accept = "image/*";
      hiddenDataLabel.style.display = "block";
      hiddenDataTextarea.style.display = "block";
    } else if (encodingType === "image") {
      coverFileInput.accept = "image/*";
      hiddenFileUploadLabel.style.display = "block";
      hiddenFileInput.style.display = "block";
      hiddenFileInput.accept = "image/*";
    } else if (encodingType === "video") {
      coverFileInput.accept = "video/*";
      hiddenFileTypeLabel.style.display = "block";
      hiddenFileTypeSelect.style.display = "block";
      hiddenFileTypeDesc.style.display = "block";

      if (hiddenFileType === "text") {
        hiddenDataLabel.style.display = "block";
        hiddenDataTextarea.style.display = "block";
      } else if (hiddenFileType === "image") {
        hiddenFileUploadLabel.style.display = "block";
        hiddenFileInput.style.display = "block";
        hiddenFileInput.accept = "image/*";
      } else if (hiddenFileType === "video") {
        hiddenVideoUploadLabel.style.display = "block";
        hiddenVideoInput.style.display = "block";
        hiddenVideoInput.accept = "video/*";
      }
    }
  }

  encodingTypeSelect.addEventListener("change", updateEncodingInputs);
  hiddenFileTypeSelect.addEventListener("change", updateEncodingInputs);

  encodeTab.addEventListener("click", () => switchTab("encode"));
  decodeTab.addEventListener("click", () => switchTab("decode"));

  function resetEncodeDownloadLink() {
    downloadLink.href = "#";
    downloadLink.style.display = "none";
    downloadLink.removeAttribute("download");
  }
  function resetDecodeDownloadLink() {
    downloadDecodedImage.href = "#";
    downloadDecodedImage.style.display = "none";
    downloadDecodedImage.removeAttribute("download");
  }
  function resetResponseText() {
    responseText.textContent = "";
    responseText.style.display = "none";
  }

  async function encodeFile() {
    resetEncodeDownloadLink();

    const encodingType = encodingTypeSelect.value;
    const hiddenFileType = hiddenFileTypeSelect.value;

    if (!coverFileInput.files.length) {
      alert("Please select a cover file (image or video)");
      return;
    }
  
    const formData = new FormData();

    function convertImageToPNG(file) {
      return new Promise((resolve) => {
        const img = new Image();
        const reader = new FileReader();
        reader.onload = (e) => {
          img.onload = () => {
            const canvas = document.createElement("canvas");
            canvas.width = img.width;
            canvas.height = img.height;
            const ctx = canvas.getContext("2d");
            ctx.drawImage(img, 0, 0);
            canvas.toBlob((blob) => {
              const pngFile = new File([blob], "converted.png", { type: "image/png" });
              resolve(pngFile);
            }, "image/png");
          };
          img.src = e.target.result;
        };
        reader.readAsDataURL(file);
      });
    }

    try {
      showFullscreenLoader();

      if (encodingType === "text") {
        if (!hiddenDataTextarea.value.trim()) {
          alert("Please enter text to hide");
          return;
        }
        const pngCover = await convertImageToPNG(coverFileInput.files[0]);
        formData.append("image", pngCover);
        formData.append("text", hiddenDataTextarea.value.trim());

      } else if (encodingType === "image") {
        if (!hiddenFileInput.files.length) {
          alert("Please select an image file to hide");
          return;
        }
        const pngCover = await convertImageToPNG(coverFileInput.files[0]);
        const pngHidden = await convertImageToPNG(hiddenFileInput.files[0]);
        formData.append("cover_image", pngCover);
        formData.append("image", pngHidden);

      } else if (encodingType === "video") {
        formData.append("video", coverFileInput.files[0]);

        if (hiddenFileType === "text") {
          if (!hiddenDataTextarea.value.trim()) {
            alert("Please enter text to hide in video");
            return;
          }
          formData.append("text", hiddenDataTextarea.value.trim());

        } else if (hiddenFileType === "image") {
          const pngHidden = await convertImageToPNG(hiddenFileInput.files[0]);
          formData.append("hidden_image", pngHidden);

        } else if (hiddenFileType === "video") {
          formData.append("hidden_video", hiddenVideoInput.files[0]);
        }
      }

      const response = await fetch("https://pixelsafe.onrender.com/encode", {
        method: "POST",
        body: formData,
      });
  
      if (!response.ok) {
        const errorData = await response.json();
        alert("Error: " + errorData.error);
        return;
      }

      const contentType = response.headers.get("content-type");
      if (!contentType.includes("image") && !contentType.includes("video")) {
        alert("Unexpected server response");
        return;
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      downloadLink.href = url;
      downloadLink.style.display = "inline-block";
      downloadLink.download = contentType.includes("video") ? "encoded_video.mp4" : "encoded_image.png";

    } catch (error) {
      alert("An error occurred: " + error.message);
      console.error(error);
    } finally {
      hideFullscreenLoader();
    }
  }

  decodeTypeSelect.addEventListener("change", () => {
    resetDecodeDownloadLink();
    resetResponseText();
    dataType.style.display = "none";
    dataTypeDesc.style.display = "none";

    selectedValue = decodeTypeSelect.value;

    if (selectedValue === "video") {
      dataType.style.display = "block";
      dataTypeDesc.style.display = "block";
    }
  });

  async function decodeFile() {
    resetDecodeDownloadLink();
    resetResponseText();

    const file = decodeFileInput.files[0];
    if (!file) {
      alert("Please select a file to decode");
      return;
    }

    const decodeType = decodeTypeSelect.value;

    try {
      showFullscreenLoader();

      const formData = new FormData();
      formData.append("file", file);
      formData.append("decode_type", decodeType); // text, image, or video

      const response = await fetch("https://pixelsafe.onrender.com/decode", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        alert("Error: " + errorData.error);
        return;
      }

      const contentType = response.headers.get("content-type");

      if (contentType.includes("application/json")) {
        const data = await response.json();
        if (data.decoded_text) {
          responseText.textContent = "Decoded Text: " + data.decoded_text;
          responseText.style.display = "block";
        } else {
          alert("No decoded text found in response.");
        }
      } else if (contentType.includes("image")) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        downloadDecodedImage.href = url;
        downloadDecodedImage.style.display = "inline-block";
        downloadDecodedImage.download = "decoded_image.png";
      } else if (contentType.includes("video")) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        downloadDecodedImage.href = url;
        downloadDecodedImage.style.display = "inline-block";
        downloadDecodedImage.download = "decoded_video.mp4";
      } else if (contentType.includes("application/octet-stream")) {
        // generic binary file (e.g., hidden file from ZIP)
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        downloadDecodedImage.href = url;
        downloadDecodedImage.style.display = "inline-block";
        downloadDecodedImage.download = "hidden_file";
      } else {
        alert("Unexpected response type: " + contentType);
      }
    } catch (error) {
      alert("An error occurred while decoding: " + error.message);
      console.error(error);
    } finally {
      hideFullscreenLoader();
    }
  }

  encodeForm.addEventListener("submit", (e) => {
    e.preventDefault();
    encodeFile();
  });

  decodeForm.addEventListener("submit", (e) => {
    e.preventDefault();
    decodeFile();
  });

  decodeTypeSelect.addEventListener("change", () => {
    resetDecodeDownloadLink();
    resetResponseText();
  });

  updateEncodingInputs(); // initialize inputs on load
});
