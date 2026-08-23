/**
 * NewProject page — Hosts the multi-step project creation wizard.
 */

import MultiStepForm from '../components/MultiStepForm/MultiStepForm';
import './NewProject.css';

export default function NewProject() {
  return (
    <div className="new-project page">
      <MultiStepForm />
    </div>
  );
}
