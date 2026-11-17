#pragma once
constexpr int HOME_ANGLE = 0;
constexpr int ANGLES[8] = {20,40,60,80,100,120,140,160};
inline bool validStep(int position,int compartment,int angle) {
 return position>=0 && position<8 && compartment==position+1 && angle==ANGLES[position];
}
enum class Action { Wait, Move, Acknowledge };
inline Action nextAction(int phase,bool sameEvent,bool home,bool emptyConfirmed,bool aligned) {
 if(phase==2 || sameEvent)return Action::Acknowledge;
 if(phase!=0)return Action::Wait;
 if(home)return emptyConfirmed?Action::Move:Action::Wait;
 return aligned?Action::Move:Action::Wait;
}
inline int phaseAfterRestart(int phase) {return phase==1?2:phase;}
