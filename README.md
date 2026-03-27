# UIForge

**UIForge** is a personal developer tool that converts UI screenshots into structured components and generates React Native or HTML layouts automatically.

The goal of the project is not full automation, but accelerating manual UI development by reconstructing interface structure, styles, and components directly from images.

---

## ✨ Features

* Detect UI elements from screenshots

  * buttons
  * cards
  * text blocks
  * images
  * icons
  * containers

* Automatic component segmentation

* Visual style extraction

  * colors
  * gradients
  * shadows
  * borders
  * corner radius

* Layout reconstruction

* Code generation

  * React Native components
  * HTML layouts

---

## 🧠 How It Works

```
Screenshot
   ↓
UI Detection
   ↓
Component Segmentation
   ↓
Style Extraction
   ↓
Layout Reconstruction
   ↓
Code Generation
```

The system builds an intermediate **UI JSON AST**, which acts as a platform-agnostic representation of the interface.

This allows generating UI code for different targets from the same source.

---

## 🎯 Project Goals

* Reduce repetitive UI coding
* Speed up prototyping
* Reverse engineer existing interfaces
* Experiment with AI-assisted UI development

This project is designed as a **personal engineering tool**, not a commercial product.

---

## 🧱 Tech Stack

* Vision LLM API for UI understanding
* OpenCV for image processing
* OCR for text extraction
* Custom layout inference engine
* LLM-based code generation

---

## ⚠️ Philosophy

UIForge does **not** aim for pixel-perfect automatic generation.

Instead, it produces **80% ready components** that developers can quickly refine.

---

## 🚧 Status

Experimental / Work in Progress.

---

## 📜 License

MIT
