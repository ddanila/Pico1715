// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
// Four-phase parallel link. A staged record survives a link resynchronization.
module analyzer_link(
 input wire clk, reset_n, sync_n, ack, capture_enable, capture_idle,
 input wire [8:0] queued,
 input wire [31:0] dropped, filtered,
 input wire [9:0] capture_mask,
 output wire read_enable,
 input wire read_valid,
 input wire [127:0] read_record,
 output wire [7:0] data,
 output wire [4:0] byte_index,
 output wire request,
 output reg [31:0] sent_records
);
 reg [1:0] sync_pipe, ack_pipe, phase;
 reg pending, staged, crc_ready, status_sent, ever_started;
 reg [159:0] frame;
 reg [15:0] crc;
 reg [4:0] index, crc_index;
 function automatic [15:0] crc_byte(input [15:0] old_crc,input [7:0] value);
  reg [15:0] c;integer i;
  begin c=old_crc^{value,8'b0};
   for(i=0;i<8;i=i+1)c=c[15]?(c<<1)^16'h1021:c<<1;
   crc_byte=c;
  end
 endfunction
 wire [7:0] data_byte=frame[index*8 +: 8];
 wire [7:0] crc_data_byte=frame[crc_index*8 +: 8];
 assign data=index<20?data_byte:(index==20?crc[7:0]:crc[15:8]);
 assign byte_index=index;
 assign request=staged && phase==1 && sync_pipe[1];
 assign read_enable=sync_pipe[1] && !ack_pipe[1] && phase==0 && !staged && !pending && queued!=0;
 always @(posedge clk or negedge reset_n) begin
  if(!reset_n) begin
   sync_pipe<=0;ack_pipe<=0;phase<=0;pending<=0;staged<=0;crc_ready<=0;
   status_sent<=0;ever_started<=0;frame<=0;crc<=16'hffff;index<=0;crc_index<=0;sent_records<=0;
  end else begin
   sync_pipe<={sync_pipe[0],sync_n};ack_pipe<={ack_pipe[0],ack};
   if(capture_enable)ever_started<=1;
   if(read_enable)pending<=1;
   if(read_valid) begin
    pending<=0;staged<=1;frame<={read_record,32'h00000101};
    crc<=16'hffff;crc_index<=0;crc_ready<=0;
   end else if(!staged && !pending && phase==0 && ever_started &&
               !capture_enable && capture_idle && queued==0 && !status_sent) begin
    staged<=1;frame<={22'd0,capture_mask,sent_records,filtered,dropped,
                     8'd0,6'd0,(dropped!=0),1'b1,8'd1,8'd2};
    crc<=16'hffff;crc_index<=0;crc_ready<=0;
   end else if(staged && !crc_ready) begin
    crc<=crc_byte(crc,crc_data_byte);
    if(crc_index==19)crc_ready<=1;
    else crc_index<=crc_index+1'b1;
   end
   if(!sync_pipe[1])begin phase<=0;index<=0;end
   else case(phase)
    0:if(staged && crc_ready && !ack_pipe[1])begin phase<=1;index<=0;end
    1:if(ack_pipe[1]) begin
     phase<=2;
     if(index==21)begin
      staged<=0;
      if(frame[7:0]==1)sent_records<=sent_records+1'b1;
      else status_sent<=1;
     end
    end
    2:if(!ack_pipe[1])begin
     if(staged)begin index<=index+1'b1;phase<=1;end
     else phase<=0;
    end
    default:phase<=0;
   endcase
  end
 end
endmodule
