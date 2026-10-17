"""Generate a public demonstration from actual domain guards and synthetic data."""
import json
import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.database import Base
from src import models, companies, evidence
from src.enums import CompanyStage, EvidenceClassification
from src.schemas import CompanyIn, EvidenceIn
from src.stages import StageTransitionError

def generate():
    scenarios=[]
    for label, classification in [
        ('No supporting evidence',None),
        ('Unsupported assumption',EvidenceClassification.UNSUPPORTED_ASSUMPTION),
        ('Research inference',EvidenceClassification.INFERENCE),
        ('Confirmed synthetic fact',EvidenceClassification.CONFIRMED_FACT),
    ]:
        engine=create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            company,_=companies.create_or_get_company(session,CompanyIn(company_name='Example Manufacturing',website='https://manufacturer.example'))
            if classification:
                evidence.add_evidence(session,EvidenceIn(company_id=company.company_id,evidence_text='Synthetic demonstration of a company-fit observation.',classification=classification,source_name='Synthetic fixture'))
            try:
                companies.advance_company_stage(session,company.company_id,CompanyStage.ICP_APPROVED)
                approved=True;reason='Research approval gate accepted the structured evidence.'
            except StageTransitionError as exc:
                approved=False;reason=str(exc)
            qualifies=bool(classification and evidence.is_actionable_for_qualification(classification))
            scenarios.append({'name':label,'summary':reason,'rows':[
                ['Research approval','Accepted' if approved else 'Blocked'],
                ['Classification may support commercial qualification','Yes' if qualifies else 'No'],
                ['Actual opportunity created','No, additional opportunity guards still apply'],
                ['Company record','Synthetic .example company'],
            ],'trace':{'classification':classification.value if classification else None,'research_approved':approved,'qualifying_classification':qualifies,'scope':'Classification eligibility does not by itself create an opportunity or verify factual truth.'}})
        engine.dispose()
    return {'kind':'crm','input_type':'synthetic fixtures; no client data','scenarios':scenarios}

if __name__=='__main__':
    target=Path(__file__).with_name('evidence.json')
    target.write_text(json.dumps(generate(),indent=2)+'\n')
    print(target.name)
