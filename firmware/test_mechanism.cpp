#include "MediTrack/mechanism.h"
#include <cassert>
int main(){
 for(int p=0;p<8;p++){assert(validStep(p,p+1,(p+1)*20));assert(!validStep(p,p+2,(p+1)*20));}
 assert(!validStep(8,1,20));assert(HOME_ANGLE==0);
 assert(nextAction(0,false,false,false,false)==Action::Wait); // reboot: no alignment
 assert(nextAction(0,false,false,false,true)==Action::Move);
 assert(nextAction(0,true,false,false,true)==Action::Acknowledge); // duplicate
 assert(nextAction(2,false,false,false,true)==Action::Acknowledge); // lost confirm
 assert(phaseAfterRestart(1)==2); // interrupted movement must be reported
 assert(nextAction(phaseAfterRestart(1),false,false,false,false)==Action::Acknowledge);
 assert(nextAction(0,false,true,false,true)==Action::Wait); // no loaded return
 assert(nextAction(0,false,true,true,false)==Action::Move); // inspected empty return
}
