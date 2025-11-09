import { useState } from "react";
import { FaPlay, FaPause } from "react-icons/fa";
import { BsRecordCircle } from "react-icons/bs";

export default function RecordButton({ onToggle, recording }) {
    
   return (
        <>            
            <button
                className={`text-white font-bold py-8 px-8 rounded-full ${recording ? "bg-red-500 hover:bg-red-700" : "bg-gray-500 hover:bg-gray-700"}`}
                style={{ cursor: "pointer" }}
                onClick={onToggle}
            >{recording ? <BsRecordCircle /> : <FaPause />}</button>
        </>
    )
}