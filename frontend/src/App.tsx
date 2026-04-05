import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import ChallengePage from "@/pages/ChallengePage";
import FlagsPage from "@/pages/FlagsPage";
import SubmitPage from "@/pages/SubmitPage";
import Competitions from "@/pages/Competitions";
import Settings from "@/pages/Settings";
import CompetitionProfile from "@/pages/CompetitionProfile";
import AWDOverview from "@/pages/awd/AWDOverview";
import AWDExploits from "@/pages/awd/AWDExploits";
import AWDPatches from "@/pages/awd/AWDPatches";
import AWDHostMap from "@/pages/awd/AWDHostMap";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="challenge/:cat/:name" element={<ChallengePage />} />
          <Route path="flags" element={<FlagsPage />} />
          <Route path="submit" element={<SubmitPage />} />
          <Route path="competitions" element={<Competitions />} />
          <Route path="competitions/:dir" element={<CompetitionProfile />} />
          <Route path="settings" element={<Settings />} />
          <Route path="awd" element={<AWDOverview />} />
          <Route path="awd/:service/exploits" element={<AWDExploits />} />
          <Route path="awd/:service/patches" element={<AWDPatches />} />
          <Route path="awd/:service/hosts" element={<AWDHostMap />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
