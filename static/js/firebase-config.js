import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-auth.js";

const firebaseConfig = {
    apiKey: "AIzaSyBOiowcB0phqUiNxXs2Z9CpfSI_1Q6wpho",
    authDomain: "jobapptracker-aefd6.firebaseapp.com",
    projectId: "jobapptracker-aefd6",
    storageBucket: "jobapptracker-aefd6.firebasestorage.app",
    messagingSenderId: "548919893131",
    appId: "1:548919893131:web:d64209d3c94b2b4e31488e",
    measurementId: "G-5HQKCRC59S"
  };
  const app = initializeApp(firebaseConfig);
  const auth = getAuth(app);

// ✅ Export firebaseConfig too
export { firebaseConfig, signInWithPopup, signOut, onAuthStateChanged };