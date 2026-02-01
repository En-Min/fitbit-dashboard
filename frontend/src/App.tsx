import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Overview from "./pages/Overview";
import HeartRate from "./pages/HeartRate";
import Sleep from "./pages/Sleep";
import Activity from "./pages/Activity";
import Glucose from "./pages/Glucose";
import Correlations from "./pages/Correlations";
import Settings from "./pages/Settings";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Overview />} />
          <Route path="/heart-rate" element={<HeartRate />} />
          <Route path="/sleep" element={<Sleep />} />
          <Route path="/activity" element={<Activity />} />
          <Route path="/glucose" element={<Glucose />} />
          <Route path="/correlations" element={<Correlations />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
