console.log("✅ login.js loaded");

import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup
} from "https://www.gstatic.com/firebasejs/10.8.0/firebase-auth.js";
import { firebaseConfig } from "./firebase-config.js";

// 🔥 Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const provider = new GoogleAuthProvider();

// 🎯 Add login button listener
document.addEventListener("DOMContentLoaded", () => {
  const loginBtn = document.getElementById("google-login-btn");
  if (!loginBtn) return console.error("Login button not found");

  loginBtn.addEventListener("click", () => {
    signInWithPopup(auth, provider)
      .then(async (result) => {
        const user = result.user;
        const idToken = await user.getIdToken(); // 👈 Get Firebase token

        console.log("✅ Logged in as:", user.displayName);

        // 🔐 Send token to Flask backend
        const res = await fetch("/sessionLogin", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            idToken,
            email: user.email,
            name: user.displayName,
            picture: user.photoURL,
            locale: user.reloadUserInfo?.language || "en",
            gender: "Not provided",
            theme: "dark",  // default
            email_alerts: false
          })
        });

        if (res.ok) {
          window.location.href = "/dashboard"; // 🎯 Redirect if success
        } else {
          alert("Backend login failed.");
        }
      })
      .catch((error) => {
        console.error("❌ Login failed:", error.message);
        alert("Login failed.");
      });
  });
});